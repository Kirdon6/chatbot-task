import duckdb
import pandas as pd

class Validator:
    """
    Validates SQL queries for security and correctness.
    
    Blocks:
    - Data modification operations (DROP, DELETE, UPDATE, etc.)
    - Multiple statements 
    - Non-SELECT queries
    - Queries not targeting the 'df' dataframe
    """
    
    def __init__(self) -> None:
        pass

    UNSAFE_KEYWORDS = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 
        'CREATE', 'TRUNCATE', 'REPLACE', 'MERGE',
        'GRANT', 'REVOKE', 'EXECUTE', 'EXEC'
    ]

    def validate_query(self, query: str) -> tuple[bool, str]:
        """
        Validate the SQL query for security and correctness.
        """
        
        for keyword in self.UNSAFE_KEYWORDS:
            if keyword in query.upper():
                return False, f"Unsafe keyword: {keyword}"
        
        if ";" in query.rstrip(';'):
            return False, "Semicolon is not allowed"
        
        if not query.strip().startswith("SELECT"):
            return False, "Only SELECT queries are allowed"
        
        if 'FROM' in query.upper():

            if 'FROM DF' not in query.upper():
                return False, "Query must reference the dataframe 'df' only"

        return True, "Query is valid"
