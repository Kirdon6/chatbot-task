Marketing Data Chatbot - Technical Proposal
Executive Summary
A containerized Python chatbot that enables natural language querying of marketing performance data through a two-stage LLM pipeline: text-to-SQL generation followed by natural language response formatting. The system maintains conversation context, handles follow-up questions, and implements robust SQL validation for data security.

1. System Architecture
1.1 High-Level Design
┌──────────────────────────────────────────────────────────────┐
│                        User Input                             │
│              "Top 5 campaigns by revenue in Q2 2023?"         │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                  Conversation Manager                         │
│  • Maintains history (question, SQL, assistant response)      │
│  • Monitors token usage via API responses                     │
│  • Triggers summarization at 85-90% capacity                  │
│  • Keeps last 3 turns uncompressed                           │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   Stage 1: Text-to-SQL                        │
│  Model: Claude Sonnet 4.5                                     │
│  Input: User question + conversation history + schema         │
│  Output: SQL query                                            │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    SQL Validator                              │
│  • Block: DROP, DELETE, UPDATE, INSERT, ALTER, etc.          │
│  • Detect multiple statements (;)                             │
│  • Verify single table access only                            │
│  • On failure: Retry (max 3x) or request user rephrase       │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   Query Execution                             │
│  Engine: DuckDB                                               │
│  Data: marketing_data.csv (12k rows)                         │
│  Safety: Read-only mode                                       │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              Stage 2: Result-to-Natural Language              │
│  Model: Claude Sonnet 4.5 (different system prompt)          │
│  Input: Original question + SQL results                       │
│  Output: Natural language answer                              │
│  Note: Large result sets handled via truncation/summary       │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                      Logging System                           │
│  • Each conversation → separate .txt log file                 │
│  • Logs: timestamps, user input, SQL, results, responses      │
│  • SQL queries NOT exposed to user (logs only)                │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
                      User receives answer
1.2 Technology Stack
Core Components:

Language: Python 3.11
LLM Provider: Anthropic Claude API

SQL Generation: claude-sonnet-4-20250514
Response Formatting: claude-sonnet-4-20250514 (different system prompt)


SQL Engine: DuckDB (in-memory, read-only mode)
Data Processing: Pandas
Containerization: Docker

Dependencies:
txtanthropic>=0.18.0
duckdb>=0.9.0
pandas>=2.0.0
python-dotenv>=1.0.0

2. Conversation Management
2.1 History Structure
pythonconversation_history = [
    {
        "turn": 1,
        "user_question": "Total revenue in 2024?",
        "generated_sql": "SELECT SUM(Revenue) FROM marketing_data WHERE Year = 2024",
        "assistant_response": "The total revenue in 2024 was $45.2 million.",
        "timestamp": "2024-02-14T10:30:00",
        "tokens_used": {"input": 1200, "output": 150}
    },
    # ... more turns
]
2.2 Context Window Management
Token Budget Strategy:
pythonMAX_CONTEXT_TOKENS = 180,000  # Claude Sonnet 4.5 limit
RESERVED_FOR_OUTPUT = 2,000
RESERVED_FOR_SCHEMA = 1,500
RESERVED_FOR_SYSTEM = 500
AVAILABLE_FOR_HISTORY = 176,000

SUMMARIZATION_THRESHOLD = 0.85  # 85% of available tokens
Summarization Rules:

Trigger: When conversation history exceeds 85% of available tokens (tracked via API responses)
Strategy:

Keep last 3 turns verbatim (uncompressed)
Summarize all older turns into condensed context
Summarization performed by Claude Sonnet 4.5


Fallback: If summarization insufficient, truncate oldest summaries first

Example Summarization Prompt:
python"""
Summarize the following conversation history into a concise context summary.
Focus on: filters applied, metrics queried, time periods discussed.
Preserve information needed for potential follow-up questions.

History to summarize:
{old_turns}

Output a 2-3 sentence summary.
"""

3. SQL Generation & Validation
3.1 Schema Definition
Precalculated metadata provided in every SQL generation prompt:
pythonSCHEMA_CONTEXT = """
Table: marketing_data
Columns:
- Year (integer): 2020-2023
- Quarter (string): Format "YYYY QN" (e.g., "2023 Q2")
- Month (string): Format "YYYYMNN" (e.g., "2023M06")
- Week (integer): Week number (1-53)
- Date (date): Format YYYY-MM-DD
- Country (string): "DK" (Denmark)
- "Media Category" (string): "online" or "offline"
- "Media Name" (string): e.g., "YouTube Trueview Ads", "Radio"
- Communication (string): "Tactical" or "Branding"
- "Campaign Category" (string): "Category 1" through "Category 11"
- Product (string): "Product 1" through "Product 14"
- "Campaign Name" (string): e.g., "Campaign 1", "Campaign 328"
- Revenue (float): Revenue in DKK
- Cost (float): Marketing spend in DKK

Calculated Metrics:
- Profit = Revenue - Cost
- ROI = (Revenue - Cost) / Cost * 100

Important Notes:
- Column names with spaces MUST be quoted (e.g., "Media Category")
- Latest data available: 2023 Q3 (most recent quarter)
- "Last quarter" refers to 2023 Q3
- "This year" refers to 2023
- For "top N" queries, use ORDER BY DESC LIMIT N
"""
3.2 System Prompts
Stage 1: Text-to-SQL
pythonSQL_GENERATION_PROMPT = """
You are a SQL expert for marketing analytics. Generate ONLY valid DuckDB SQL queries.

{schema_context}

Rules:
1. Output ONLY the SQL query, no explanations or markdown
2. Use proper aggregations: SUM() for totals, AVG() for averages, COUNT() for counts
3. For rankings/top N: ORDER BY [metric] DESC LIMIT N
4. For trends over time: include time dimension in SELECT
5. Calculate profit as (Revenue - Cost)
6. Always quote column names with spaces
7. Use ONLY the marketing_data table

If the user asks a follow-up (e.g., "same but for Product 1"), modify the previous query.

{conversation_history}

Current question: {user_question}

SQL query:
"""
Stage 2: Result-to-Text
pythonRESPONSE_GENERATION_PROMPT = """
You are a helpful marketing analytics assistant. Convert SQL query results into natural, conversational language.

Rules:
1. Be concise but informative
2. Format numbers appropriately (e.g., $45.2M, 23.4%, 1,234 campaigns)
3. For trends, describe the pattern (increasing, decreasing, stable)
4. For rankings, list top items clearly
5. If results are empty, say "No data found matching those criteria"
6. Do NOT mention SQL or technical details

User question: {user_question}
Query results: {sql_results}

Natural language response:
"""
3.3 SQL Validation
Blocked Operations:
pythonUNSAFE_KEYWORDS = [
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 
    'CREATE', 'TRUNCATE', 'REPLACE', 'MERGE',
    'GRANT', 'REVOKE', 'EXECUTE', 'EXEC'
]

def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Returns: (is_valid, error_message)
    """
    sql_upper = sql.upper().strip()
    
    # Check 1: Blocked operations
    for keyword in UNSAFE_KEYWORDS:
        if keyword in sql_upper:
            return False, f"SQL contains unsafe operation: {keyword}"
    
    # Check 2: Multiple statements
    if ';' in sql.rstrip(';'):  # Allow trailing semicolon
        return False, "Multiple SQL statements not allowed"
    
    # Check 3: Only SELECT statements
    if not sql_upper.startswith('SELECT'):
        return False, "Only SELECT queries are permitted"
    
    # Check 4: Table name validation
    if 'FROM' in sql_upper:
        # Extract table name and verify it's marketing_data
        # Simple check - could be improved with SQL parsing
        if 'marketing_data' not in sql.lower():
            return False, "Query must use marketing_data table only"
    
    return True, ""
Retry Logic:
pythonMAX_SQL_RETRIES = 3

def generate_sql_with_retry(user_question, history):
    error_context = ""
    
    for attempt in range(MAX_SQL_RETRIES):
        sql = call_llm_for_sql(user_question, history, error_context)
        
        is_valid, error_msg = validate_sql(sql)
        
        if is_valid:
            # Additional validation: try EXPLAIN
            try:
                duckdb.execute(f"EXPLAIN {sql}")
                return sql
            except Exception as e:
                error_context = f"SQL syntax error: {str(e)}"
        else:
            error_context = f"Validation failed: {error_msg}"
    
    # After 3 failures, ask user to rephrase
    raise SQLGenerationError(
        "Could not generate valid SQL after 3 attempts. "
        "Please rephrase your question."
    )

4. Error Handling
4.1 Error Categories & Responses
Error TypeHandling StrategyUser MessageInvalid SQL generationRetry up to 3 times with error feedback"I had trouble understanding your question. Could you rephrase it?"SQL validation failureBlock execution, ask for rephrase"I cannot process queries that modify data. Please ask an analysis question."Empty result setReturn gracefully"No data found matching your criteria."Large result set (>1000 rows)Truncate and summarize"Found X results. Here's a summary: [top 10 + statistics]"API rate limitExponential backoff retry (3 attempts)"Service temporarily busy. Retrying..."API failureGraceful degradation"I'm having trouble connecting. Please try again."Non-data questionRedirect politely"I can only answer questions about the marketing data. Please ask about campaigns, revenue, costs, or performance metrics."Token limit exceeded (post-summarization)Truncate oldest turns"Conversation is very long. Some early context may be lost."
4.2 Large Result Handling
pythondef handle_large_results(df: pd.DataFrame, max_rows: int = 100) -> str:
    """
    If results exceed max_rows, return summary + top N
    """
    if len(df) <= max_rows:
        return df.to_string(index=False)
    
    summary = f"Total rows: {len(df)}\n\n"
    summary += "Top 10 results:\n"
    summary += df.head(10).to_string(index=False)
    summary += f"\n\n[{len(df) - 10} additional rows omitted]"
    
    # Add aggregate statistics if numeric columns present
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        summary += "\n\nSummary statistics:\n"
        summary += df[numeric_cols].describe().to_string()
    
    return summary

5. Logging System
5.1 Log Structure
Each conversation session creates a timestamped log file:
Filename format: conversation_YYYYMMDD_HHMMSS.txt
Log content:
txt============================================================
MARKETING CHATBOT CONVERSATION LOG
Started: 2024-02-14 10:30:45
============================================================

[Turn 1] 10:30:52
User: Total revenue in 2024?

Generated SQL:
SELECT SUM(Revenue) FROM marketing_data WHERE Year = 2024

Query Execution: SUCCESS (0.12s)
Result: 45234567.89

Assistant Response:
The total revenue in 2024 was $45.2 million.

Tokens Used: Input=1,245 | Output=156 | Total=1,401
-----------------------------------------------------------

[Turn 2] 10:31:15
User: Same but for Q2 only

Generated SQL:
SELECT SUM(Revenue) FROM marketing_data 
WHERE Year = 2024 AND Quarter = '2024 Q2'

Query Execution: SUCCESS (0.08s)
Result: 12456789.12

Assistant Response:
In Q2 2024, the total revenue was $12.5 million.

Tokens Used: Input=1,567 | Output=142 | Total=1,709
-----------------------------------------------------------

[SUMMARIZATION TRIGGERED] 10:35:30
Reason: Token usage reached 85% threshold (153,000/176,000 tokens)
Turns summarized: 1-5
Turns kept verbatim: 6-8 (last 3 turns)

Summary of turns 1-5:
User queried total revenue for 2024 ($45.2M), then filtered by Q2 
($12.5M), then asked for top campaigns by profit (showed top 5), 
then filtered for Product 1 only, then asked about media category 
breakdown for online vs offline.
-----------------------------------------------------------

... conversation continues ...

============================================================
CONVERSATION ENDED: 2024-02-14 10:45:30
Total Turns: 12
Total Tokens: 24,567
Summarizations: 1
============================================================
5.2 Logging Implementation
pythonimport logging
from datetime import datetime
from pathlib import Path

class ConversationLogger:
    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"conversation_{timestamp}.txt"
        
        self._write_header()
    
    def log_turn(self, turn_num, user_input, sql, result, 
                 response, tokens, execution_time):
        # Implementation details...
        pass
    
    def log_summarization(self, reason, turns_summarized, 
                          turns_kept, summary_text):
        # Implementation details...
        pass

6. Docker Configuration
6.1 Dockerfile
dockerfile# Multi-stage build explanation:
# Stage 1 (builder): Install dependencies, create optimized environment
# Stage 2 (runtime): Copy only necessary files, minimal image size
# Benefits: Faster builds (caching), smaller final image, better security

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY chatbot.py .
COPY marketing_data.csv ./data/

# Ensure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Create logs directory
RUN mkdir -p /app/logs

# Run as non-root user for security
RUN useradd -m -u 1000 chatbot && \
    chown -R chatbot:chatbot /app
USER chatbot

# Set environment variable for API key (provided at runtime)
ENV ANTHROPIC_API_KEY=""

ENTRYPOINT ["python", "chatbot.py"]
Why multi-stage build?

Smaller image: Builder stage discarded (~200MB saved)
Faster rebuilds: Dependency layer cached separately
Security: No build tools in final image
Best practice: Industry standard for production containers

6.2 Docker Compose (Optional)
yamlversion: '3.8'

services:
  chatbot:
    build: .
    image: marketing-chatbot:latest
    container_name: marketing-chatbot
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      # Mount logs directory for persistence
      - ./logs:/app/logs:rw
      # Optional: mount data if you want to update CSV without rebuild
      - ./marketing_data.csv:/app/data/marketing_data.csv:ro
    stdin_open: true
    tty: true
6.3 Usage
bash# Build image
docker build -t marketing-chatbot .

# Run with API key
docker run -it \
  -e ANTHROPIC_API_KEY=sk-ant-xxx \
  -v $(pwd)/logs:/app/logs \
  marketing-chatbot

# Or with docker-compose
export ANTHROPIC_API_KEY=sk-ant-xxx
docker-compose up
```

---

## 7. Project Structure
```
marketing-chatbot/
├── .env.example                 # Template for environment variables
├── .gitignore                   # Exclude logs, .env, __pycache__
├── .dockerignore                # Exclude unnecessary files from image
├── Dockerfile                   # Multi-stage container definition
├── docker-compose.yml           # Optional orchestration
├── requirements.txt             # Python dependencies
├── README.md                    # Setup and usage instructions
├── chatbot.py                   # CLI entry point
├── marketing_data.csv           # Marketing performance dataset
│
├── src/
│   ├── __init__.py
│   ├── config.py                # Configuration, prompts, constants
│   ├── llm_client.py            # Anthropic API wrapper
│   ├── query_engine.py          # SQL generation & execution
│   ├── conversation.py          # History & summarization manager
│   ├── validator.py             # SQL validation logic
│   ├── logger.py                # Conversation logging
│   └── utils.py                 # Helper functions
│
├── logs/                        # Generated conversation logs
│   └── conversation_*.txt
│
└── tests/                       # Optional: unit tests
    ├── test_validator.py
    ├── test_query_engine.py
    └── test_conversation.py

8. Implementation Plan
Phase 1: Core Functionality (Day 1, ~4 hours)
Deliverables:

 Basic CLI chat loop
 Text-to-SQL generation (Claude Sonnet 4.5)
 DuckDB query execution
 Result-to-text formatting (Claude Sonnet 4.5, different prompt)
 Simple conversation history (no summarization)

Test criteria:

Can answer: "Total revenue in 2024?"
Can handle: "Top 5 campaigns by revenue"

Phase 2: Conversation & Validation (Day 2, ~4 hours)
Deliverables:

 SQL validation (block unsafe operations)
 Retry logic for failed SQL generation
 Token tracking via API responses
 Conversation summarization (at 85% threshold)
 Follow-up question handling

Test criteria:

Can handle: "Same but for Q2 only" (follow-up)
Blocks: "DELETE FROM marketing_data"
Summarizes: After long conversation (>10 turns)

Phase 3: Production Polish (Day 3, ~3 hours)
Deliverables:

 Logging system (conversation logs to .txt)
 Docker containerization (multi-stage build)
 Error handling for all edge cases
 Large result set handling
 README with examples

Test criteria:

All 5 example questions work correctly
Logs created and readable
Docker container runs successfully


9. Testing Strategy
9.1 Test Cases
Basic Queries:
pythontest_cases = [
    {
        "input": "Total revenue in 2024?",
        "expected_sql_contains": ["SUM(Revenue)", "Year = 2024"],
        "expected_response_contains": ["revenue", "2024"]
    },
    {
        "input": "Top 5 campaign names by revenue last quarter",
        "expected_sql_contains": ["Campaign Name", "ORDER BY", "LIMIT 5", "2023 Q3"],
        "expected_response_contains": ["top", "campaign"]
    },
    {
        "input": "Revenue and cost trend by month",
        "expected_sql_contains": ["Month", "Revenue", "Cost", "GROUP BY"],
        "expected_response_contains": ["trend", "month"]
    },
]
Follow-up Queries:
pythonfollowup_tests = [
    {
        "setup": "Total revenue in 2024?",
        "followup": "Same but for Q2 only",
        "expected_sql_contains": ["2024 Q2"]
    },
    {
        "setup": "Top 5 campaigns by profit",
        "followup": "Now only for Product 1",
        "expected_sql_contains": ["Product = 'Product 1'"]
    }
]
Edge Cases:
pythonedge_cases = [
    {
        "input": "DROP TABLE marketing_data",
        "expected": "SQLValidationError"
    },
    {
        "input": "Tell me a joke",
        "expected_response_contains": ["only answer questions about marketing data"]
    },
    {
        "input": "Revenue for year 2030",  # Future year, no data
        "expected_response_contains": ["no data found"]
    }
]
9.2 Manual Testing Script
bash# Test script for demo
You: Total revenue in 2024?
Expected: ~$45M response

You: Same but for Q2 only
Expected: ~$12M response, references Q2 2024

You: Top 5 campaigns by revenue last quarter
Expected: List of 5 campaign names with revenue figures

You: Now only for Product 1
Expected: Filtered list, mentions Product 1

You: Show me revenue and cost trend by month
Expected: Monthly breakdown or trend description

You: DROP TABLE marketing_data
Expected: Error message about unsafe operations

You: /exit
Expected: Clean exit with log file created

10. Success Criteria
10.1 Functional Requirements ✅

 Answers all 5 example questions correctly
 Handles follow-up questions ("Same but...", "Now only for...")
 Maintains conversation context
 Blocks all data-modifying SQL operations
 Generates natural language responses
 Runs in Docker container

10.2 Non-Functional Requirements ✅

 Response time: < 5 seconds per query (typical)
 Code quality: Clean, documented, follows Python best practices
 Logging: Every conversation logged to .txt file
 Error handling: Graceful failures with helpful messages
 Security: No SQL injection, no arbitrary code execution

10.3 Bonus Features (If Time Permits) ⭐

 Export conversation to JSON
 CLI commands: /reset, /history, /help
 Colored terminal output for better UX
 Unit tests with pytest
 CI/CD with GitHub Actions


11. Deployment Instructions
11.1 Prerequisites
bash# Required
- Docker 20.10+
- Anthropic API key

# Optional (for local development)
- Python 3.11+
- pip
11.2 Quick Start
bash# Clone repository
git clone <repo-url>
cd marketing-chatbot

# Set API key
export ANTHROPIC_API_KEY=sk-ant-xxx

# Build and run
docker build -t marketing-chatbot .
docker run -it -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY marketing-chatbot

# Logs will be in ./logs directory (auto-mounted)
11.3 Local Development
bash# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run locally
python chatbot.py
```

---

## 12. Estimated Costs

### 12.1 API Usage (Claude Sonnet 4.5)

**Per conversation turn:**
- Input tokens: ~2,000 (schema + history + query)
- Output tokens: ~300 (SQL + response)
- Cost per turn: ~$0.007

**For testing (20 queries):**
- Total cost: ~$0.14

**For demo/review (50 queries with follow-ups):**
- Total cost: ~$0.35

### 12.2 Infrastructure

- Docker: Free (local execution)
- Storage: Negligible (<100MB for logs)

---

## 13. Limitations & Future Enhancements

### 13.1 Current Limitations

1. **Single table only:** Cannot join with external data sources
2. **Text-only output:** No charts or visualizations
3. **Limited to dataset timeframe:** Data only available through 2023 Q3
4. **No authentication:** Single-user, local execution
5. **Stateless between sessions:** Conversation history lost on restart

### 13.2 Future Enhancements

1. **Multi-table support:** Add campaign metadata, customer segments
2. **Visualization:** ASCII charts or export to matplotlib
3. **Persistent storage:** Save conversations to SQLite
4. **Web UI:** FastAPI + React frontend
5. **Advanced analytics:** Forecasting, anomaly detection
6. **Export capabilities:** CSV, PDF report generation

---

## 14. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM generates invalid SQL | High | Validation + retry logic (max 3 attempts) |
| API rate limits | Medium | Exponential backoff, graceful degradation |
| Large result sets crash formatter | Medium | Truncate results, summary statistics |
| Context window overflow | Medium | Aggressive summarization, truncation fallback |
| User attempts SQL injection | High | Strict validation, read-only DB mode |
| Cost overrun during testing | Low | Monitor token usage, set budget alerts |

---

## 15. Conclusion

This proposal outlines a production-ready chatbot that demonstrates:

✅ **LLM Engineering Skills:** Two-stage pipeline with appropriate model usage  
✅ **Conversation Management:** Context tracking, summarization, follow-up handling  
✅ **Security:** Robust SQL validation, no data modification allowed  
✅ **Production Thinking:** Logging, error handling, containerization  
✅ **Code Quality:** Clean architecture, separation of concerns  

**Time estimate:** 8-10 hours total development  
**Complexity level:** Appropriate for take-home assignment  
**Differentiation:** Multi-stage build, conversation summarization, comprehensive logging  

---

**Appendix A: Example Conversation**
```
You: Total revenue in 2024?
Assistant: I don't have data for 2024. The dataset contains marketing data 
from 2020 through August 2023. Would you like me to show the total revenue 
for 2023 instead?

You: Yes, show me 2023 revenue
Assistant: The total revenue in 2023 was $38.5 million across all campaigns.

You: Top 5 campaigns by profit
Assistant: Here are the top 5 campaigns by profit in 2023:
1. Campaign 142 - $2.1M profit
2. Campaign 87 - $1.8M profit
3. Campaign 231 - $1.6M profit
4. Campaign 45 - $1.4M profit
5. Campaign 156 - $1.3M profit

You: Now only for Product 3
Assistant: For Product 3 specifically, the top 5 campaigns by profit were:
1. Campaign 231 - $1.6M profit
2. Campaign 287 - $890K profit
3. Campaign 134 - $720K profit
4. Campaign 98 - $650K profit
5. Campaign 203 - $580K profit

You: /exit
Goodbye! Your conversation has been saved to logs/conversation_20240214_103045.txt