import duckdb

class Validator:
    def __init__(self):
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
        
        if ";" in query:
            return False, "Semicolon is not allowed"
        
        if not query.strip().startswith("SELECT"):
            return False, "Only SELECT queries are allowed"
        
        if 'FROM' in query.upper():

            if 'df' not in query.lower():
                return False, "Query must reference the dataframe 'df' only"
        try:
            _ = duckdb.sql(query, read_only=True)
            return True, "Query is valid"
        except Exception as e:
            return False, f"Error: {e}"