from src.llm_client import LLMClient
from src.validator import Validator
from src.logger import Logger
import pandas as pd
from src.config import SQL_PROMPT, SCHEMA_CONTEXT, TEXT_RESPONSE_PROMPT, SUMMARY_PROMPT
import time
import duckdb
class ChatbotEngine:
    def __init__(self):
        self.llm_client: LLMClient = LLMClient()
        self.validator: Validator = Validator()
        self.logger: Logger = Logger()
        self.conversation_history: list[dict] = [] # add structure for the conversation history
        self.current_context = 20000 # 200000 tokens is the maximum context window size for the LLM
        self.current_context_usage = 0
        self.max_retries: int = 3
        self.max_context_usage_percentage: float = 0.1
        print("Claude: Hello! I'm here to help you with your data analysis questions. Ask me anything about the data!")
        print("Claude: For help, type 'help'")

    def run(self):
        df = pd.read_csv('marketing_data.csv')
        first_rows_of_df: str = df.head(10).to_string()
        while True:
            # Initialization of the conversation
            user_input: str = input("You: ").strip()
            self.logger.log_message(f"User input: {user_input}")
            if user_input.lower() in ["quit", "exit", "bye"]:
                print("Chatbot: Goodbye!")
                self.logger.log_message("User exited the chat")
                break
            elif user_input.lower() == "help":
                print("Claude: Available commands:")
                print("Claude: - help: Show this help message")
                print("Claude: - clear: Clear the conversation history")
                print("Claude: - quit: Exit the chat")
                print("Claude: - exit: Exit the chat")
                print("Claude: - bye: Exit the chat")
                continue
            elif user_input.lower() == "clear":
                self.conversation_history = []
                self.current_context_usage = 0
                print("Claude: Conversation history cleared")
                self.logger.log_message("Conversation history cleared")
                continue
            if not user_input:
                self.logger.log_message("User input is empty")
                continue
            
            # Format the conversation history for the LLM
            conversation_history_str: str = "\n".join(
                f"{message['role']}: {message['content']}" for message in self.conversation_history
            )
            self.logger.log_message(f"Conversation history: {conversation_history_str}")

            # Add the user input to the conversation history
            user_input_usage = self.llm_client.count_tokens(model="claude-sonnet-4-5-20250929", prompt=user_input)            
            self.conversation_history.append({"role": "user", "content": user_input, "usage": user_input_usage})
            self.current_context_usage += user_input_usage
            self.logger.log_message(f"Current context usage: {self.current_context_usage}")

            # Generate the SQL query with retries
            for i in range(self.max_retries):
                try:
                    # Check if the context usage is too high and summarize the conversation history
                    if self.current_context_usage > self.current_context * self.max_context_usage_percentage:
                        self.summarize_conversation_history()
                        self.logger.log_message(f"New Conversation History: {self.conversation_history}")

                    # Generate the SQL query
                    self.logger.log_message(f"User input: {user_input}")
                    sql_message, sql_message_output_usage = self.llm_client.generate_response_usage(
                        model="claude-sonnet-4-5-20250929",
                        prompt=SQL_PROMPT.format(question=user_input, schema=SCHEMA_CONTEXT, conversation_history=conversation_history_str, first_rows_of_df=first_rows_of_df),
                        max_tokens=1000
                    )
                    # If the SQL query is valid, execute it and generate the text response
                    if sql_message.startswith("<SQL_QUERY>"):
                        # If the SQL query is valid, add the usage to the current context usage
                        self.current_context_usage += sql_message_output_usage
                        self.logger.log_message(f"Current context usage: {self.current_context_usage}")
                        self.conversation_history.append({"role": "sql_query", "content": sql_message, "usage": sql_message_output_usage})

                        # Parse and validate the SQL query
                        query = sql_message.split("<SQL_QUERY>")[1].split("</SQL_QUERY>")[0]
                        is_valid, error_message = self.validator.validate_query(query, df)
                        if not is_valid:
                            # If the SQL query is invalid, remove it from the conversation history
                            self.conversation_history.pop()
                            user_input += f" \n Error: {error_message}. Please try again."
                            raise Exception(f"Invalid SQL query: {error_message}")

                        # Execute the SQL query
                        self.logger.log_message(f"LLM response: {query}")
                        result = duckdb.sql(query).df()

                        if len(result) >= 1000:
                            # If the result is too big, we need to truncate it
                            result = result.head(1000)

                        # If the context usage is too big, summarize the conversation history
                        if self.current_context_usage > self.current_context * self.max_context_usage_percentage:
                            self.summarize_conversation_history()
                            self.logger.log_message(f"New Conversation History: {self.conversation_history}")
                        short_conversation_history_str: str = "\n".join(
                            f"{message['role']}: {message['content']}" for message in self.conversation_history[-6:]
                        )
                        # Generate the text response
                        text_message, text_message_output_usage = self.llm_client.generate_response_usage(
                            model="claude-haiku-4-5-20251001",
                            prompt=TEXT_RESPONSE_PROMPT.format(user_question=user_input, sql_results=result.to_string(), sql_query=query, conversation_history=short_conversation_history_str),
                            max_tokens=10000
                        )

                        # Add the usage to the current context usage
                        # Log the text message and add it to the conversation history
                        self.current_context_usage += text_message_output_usage
                        self.logger.log_message(f"Text message: {text_message}")
                        self.logger.log_message(f"Current context usage: {self.current_context_usage}")
                        self.conversation_history.append({"role": "response", "content": text_message, "usage": text_message_output_usage})
                        print(f"Claude: {text_message}")
                        break
                    else:
                        # If we cannot answer the question with data, we dont need to log the LLM response
                        # in the conversation history to save tokens and prevent clutter
                        # remove the last message from the conversation history
                        last_message = self.conversation_history.pop()
                        self.current_context_usage -= last_message["usage"]
                        self.logger.log_message(f"Current context usage: {self.current_context_usage}")

                        self.logger.log_message(f"LLM response: {sql_message}")
                        print(f"Claude: {sql_message}")
                        break
                except Exception as e:
                    # If we throw an exception, we need to log the error and retry
                    # SQL query should be removed from the conversation history
                    if i == self.max_retries - 1:
                        self.logger.log_error(f"Error generating SQL message: {e}")
                        print(f"Claude: I'm sorry, I couldn't generate a valid SQL query. Try to rephrase your question.")
                    
                    time.sleep(1)
                    continue

    def summarize_conversation_history(self):
        # Summarize the conversation history
        # and remove the conversation history
        self.logger.log_message("Summarizing conversation history")
        conversation_history_str: str = "\n".join(
                f"{message['role']}: {message['content']}" for message in self.conversation_history[:-6]
            )
        summary_message, summary_message_usage = self.llm_client.generate_response_usage(
            model="claude-haiku-4-5-20251001",
            prompt=SUMMARY_PROMPT.format(conversation_history=conversation_history_str),
            max_tokens=3000
        )
        recent_history = self.conversation_history[-6:]
        self.conversation_history = []
        self.conversation_history.append({"role": "summary", "content": summary_message, "usage": summary_message_usage})
        self.conversation_history.extend(recent_history)
        self.current_context_usage = sum(message["usage"] for message in self.conversation_history)
        self.logger.log_message(f"Current context usage: {self.current_context_usage}")
