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
        self.df: pd.DataFrame = pd.read_csv('marketing_data.csv')
        self.current_context = 200000 # 200000 tokens is the maximum context window size for the LLM
        self.current_context_usage = 0
        self.max_retries: int = 3
        self.max_context_usage_percentage: float = 0.9
        print("Claude: Hello! I'm here to help you with your data analysis questions. Ask me anything about the data!")
        print("Claude: For help, type 'help'")

    def run(self):
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
            self.conversation_history.append({"role": "user", "content": user_input})

            # Generate the SQL query with retries
            for i in range(self.max_retries):
                try:
                    sql_message, sql_message_usage = self.llm_client.generate_response_usage(
                        model="claude-sonnet-4-5-20250929",
                        prompt=SQL_PROMPT.format(question=user_input, schema=SCHEMA_CONTEXT, conversation_history=conversation_history_str),
                        max_tokens=1000
                    )
                    self.current_context_usage += sql_message_usage
                    self.logger.log_message(f"SQL message usage: {sql_message_usage}")
                    if self.current_context_usage > self.current_context * self.max_context_usage_percentage:
                        self.summarize_conversation_history(conversation_history_str)

                    # If the SQL query is valid, execute it and generate the text response
                    if sql_message.startswith("<SQL_QUERY>"):
                        query = sql_message.split("<SQL_QUERY>")[1].split("</SQL_QUERY>")[0]
                        self.conversation_history.append({"role": "sql_query", "content": query})
                        is_valid, error_message = self.validator.validate_query(query)
                        if not is_valid:
                            raise Exception(f"Invalid SQL query: {error_message}")
                        result = duckdb.sql(query, read_only=True)
                        # handle large results
                        text_message, text_message_usage = self.llm_client.generate_response_usage(
                            model="claude-haiku-4-5-20251001",
                            prompt=TEXT_RESPONSE_PROMPT.format(user_question=user_input, sql_results=result),
                            max_tokens=1000
                        )
                        self.current_context_usage += text_message_usage
                        if self.current_context_usage > self.current_context * self.max_context_usage_percentage:
                            self.summarize_conversation_history(conversation_history_str)
                        print(f"Claude: {text_message}")
                        self.conversation_history.append({"role": "response", "content": text_message})
                        break
                    else:
                        print(f"Claude: {sql_message}")
                        break
                except Exception as e:
                    # If we throw an exception, we need to log the error and retry
                    # SQL query should be removed from the conversation history
                    self.conversation_history.pop()
                    if i == self.max_retries - 1:
                        self.logger.log_error(f"Error generating SQL message: {e}")
                        print(f"Claude: I'm sorry, I couldn't generate a valid SQL query. Try to rephrase your question.")
                    
                    time.sleep(1)
                    continue

    def summarize_conversation_history(self, conversation_history_str: str):
        # Summarize the conversation history
        # and remove the conversation history
        print("Claude: Summarizing conversation history")
        self.logger.log_message("Summarizing conversation history")
        self.conversation_history = []
        self.current_context_usage = 0
        summary_message, summary_message_usage = self.llm_client.generate_response_usage(
            model="claude-sonnet-4-5-20250929",
            prompt=SUMMARY_PROMPT.format(conversation_history=conversation_history_str),
            max_tokens=1000
        )
        self.current_context_usage += summary_message_usage
        self.logger.log_message(f"Summary message usage: {summary_message_usage}")
        self.conversation_history.append({"role": "summary", "content": summary_message})
