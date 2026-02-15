import duckdb
import pandas as pd

class Validator:
    def __init__(self):
        pass

    UNSAFE_KEYWORDS = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 
        'CREATE', 'TRUNCATE', 'REPLACE', 'MERGE',
        'GRANT', 'REVOKE', 'EXECUTE', 'EXEC'
    ]

    def validate_query(self, query: str, df: pd.DataFrame) -> tuple[bool, str]:
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

            if 'FROM df' not in query:
                return False, "Query must reference the dataframe 'df' only"

        return True, "Query is valid"
