from src.llm_client import LLMClient
from src.validator import Validator
from src.logger import Logger
import pandas as pd
from src.config import SQL_PROMPT, SCHEMA_CONTEXT, TEXT_RESPONSE_PROMPT, SUMMARY_PROMPT, MAX_CONTEXT_WINDOW, SUMMARIZATION_THRESHOLD, MAX_RETRIES, KEEP_RECENT_TURNS, TURN_SIZE, LARGE_RESULT_THRESHOLD, SQL_GENERATION_MODEL, TEXT_FORMATTING_MODEL, SUMMARIZATION_MODEL
import duckdb


class ChatbotEngine:
    """
    Main chatbot engine that orchestrates SQL generation, validation, 
    execution, and natural language response formatting.
    
    Uses a two-stage LLM pipeline:
    1. Claude Sonnet 4.5: Natural language -> SQL query
    2. Claude Haiku 4.5: SQL results-> Natural language response
    
    Features:
    - Conversation history management with automatic summarization
    - SQL validation for security
    - Retry logic for failed queries
    - Token usage tracking
    """

    def __init__(self) -> None:
        self.llm_client: LLMClient = LLMClient()
        self.validator: Validator = Validator()
        self.logger: Logger = Logger()
        self.conversation_history: list[dict] = []
        self.current_context: int = MAX_CONTEXT_WINDOW
        self.current_context_usage: int = 0
        self.max_retries: int = MAX_RETRIES
        self.max_context_usage_percentage: float = SUMMARIZATION_THRESHOLD
        self.large_result_threshold: int = LARGE_RESULT_THRESHOLD
        print("Claude: Hello! I'm here to help you with your data analysis questions. Ask me anything about the data!")
        print("Claude: For help, type 'help'")

    def run(self) -> None:
        df = pd.read_csv('marketing_data.csv')
        first_rows_of_df: str = df.head(5).to_string()
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
                f"{message['role'].capitalize()}: {message['content']}\n" for message in self.conversation_history
            )
            self.logger.log_message(f"Conversation history: {conversation_history_str}")

            # Add the user input to the conversation history
            user_input_usage = self.llm_client.count_tokens(model=SQL_GENERATION_MODEL, prompt=user_input)            
            self.conversation_history.append({"role": "user", "content": user_input, "usage": user_input_usage})
            self.current_context_usage += user_input_usage
            self.logger.log_message(f"Current context usage: {self.current_context_usage}")

            # Generate the SQL query with retries
            for i in range(self.max_retries):
                try:
                    # Check if the context usage is too high and summarize the conversation history
                    if self.current_context_usage > self.current_context * self.max_context_usage_percentage:
                        self.summarize_conversation_history()
                        conversation_history_str: str = "\n".join(
                            f"{message['role'].capitalize()}: {message['content']}" for message in self.conversation_history
                        )
                        self.logger.log_message(f"New Conversation History: {conversation_history_str}")

                    # Generate the SQL query
                    sql_message, sql_message_output_usage = self.llm_client.generate_response_usage(
                        model=SQL_GENERATION_MODEL,
                        prompt=SQL_PROMPT.format(question=user_input, schema=SCHEMA_CONTEXT, conversation_history=conversation_history_str, first_rows_of_df=first_rows_of_df),
                        max_tokens=1000
                    )
                    # If the SQL query is valid, execute it and generate the text response
                    if sql_message.startswith("<SQL_QUERY>"):

                        # Parse and validate the SQL query
                        query = sql_message.split("<SQL_QUERY>")[1].split("</SQL_QUERY>")[0]
                        is_valid, error_message = self.validator.validate_query(query)
                        if not is_valid:
                            # If the query is invalid, add the error message to the user input and raise an exception
                            user_input += f" \n Error: {error_message}. Please try again."
                            raise Exception(f"Invalid SQL query: {error_message}")

                        # If the query is valid, add the usage to the current context usage and the conversation history
                        self.current_context_usage += sql_message_output_usage
                        self.logger.log_message(f"Current context usage: {self.current_context_usage}")
                        self.conversation_history.append({"role": "sql_query", "content": sql_message, "usage": sql_message_output_usage})
                        # Execute the SQL query
                        self.logger.log_message(f"LLM response: {query}")

                        # DuckDB automatically detects 'df' in local scope
                        result = duckdb.sql(query).df()

                        if len(result) >= self.large_result_threshold:
                            # If the result is too big, we need to truncate it
                            result = result.head(self.large_result_threshold)
                            print(f"Claude: Result is too big, truncated to {self.large_result_threshold} rows")
                            self.logger.log_message(f"Result is too big, truncated to {self.large_result_threshold} rows")

                        # If the context usage is too big, summarize the conversation history
                        if self.current_context_usage > self.current_context * self.max_context_usage_percentage:
                            self.summarize_conversation_history()
                            conversation_history_str: str = "\n".join(
                                f"{message['role'].capitalize()}: {message['content']}" for message in self.conversation_history
                            )
                            self.logger.log_message(f"New Conversation History: {conversation_history_str}")
                        short_conversation_history_str: str = "\n".join(
                            f"{message['role']}: {message['content']}" for message in self.conversation_history[-6:]
                        )
                        # Generate the text response
                        text_message, text_message_output_usage = self.llm_client.generate_response_usage(
                            model=TEXT_FORMATTING_MODEL,
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
                    if i == self.max_retries - 1:
                        self.logger.log_error(f"Error generating SQL message: {e}")
                        print(f"Claude: I'm sorry, I couldn't generate a valid SQL query. Try to rephrase your question.")
                        break
                    continue

    def summarize_conversation_history(self) -> None:
        """
        Summarize old conversation history when approaching token limit.
        
        Keeps last 2 turns (6 messages) verbatim and summarizes everything 
        older into a condensed context.
        """

        self.logger.log_message("Summarizing conversation history")
        conversation_history_str: str = "\n".join(
                f"{message['role'].capitalize()}: {message['content']}" for message in self.conversation_history[:-(KEEP_RECENT_TURNS * TURN_SIZE)]
            )
        summary_message, summary_message_usage = self.llm_client.generate_response_usage(
            model=SUMMARIZATION_MODEL,
            prompt=SUMMARY_PROMPT.format(conversation_history=conversation_history_str),
            max_tokens=3000
        )
        recent_history = self.conversation_history[-(KEEP_RECENT_TURNS * TURN_SIZE):]
        self.conversation_history = []
        self.conversation_history.append({"role": "summary", "content": summary_message, "usage": summary_message_usage})
        self.conversation_history.extend(recent_history)
        self.current_context_usage = sum(message["usage"] for message in self.conversation_history)
        self.logger.log_message(f"Current context usage: {self.current_context_usage}")
