# Marketing Data Chatbot

A Python chatbot that enables natural language querying of marketing performance data through a two-stage LLM pipeline.

## Quick Start

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation) (package manager)

### Setup

1. **Install Poetry** (if not already installed):

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Set up environment variables**:
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env and add your Anthropic API key
   # ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

### Running the Chatbot

```bash
poetry run python chatbot.py
```

### Usage

Once running, you can:
- Ask questions about the marketing data (e.g., "What was the total revenue in 2023?")
- Use follow-up questions (e.g., "Same but for Q2 only")
- Type `help` for available commands
- Type `quit`, `exit`, or `bye` to exit

---

## Architecture

### Two-Stage LLM Pipeline

1. **Text-to-SQL** (Claude Sonnet 4.5)
   - Converts natural language to SQL queries
   - Uses conversation history for follow-up questions
   - Output: Validated SQL query

2. **SQL-to-Text** (Claude Haiku 4.5)
   - Formats query results into natural language
   - Provides context-aware responses
   - Output: User-friendly answer

### Conversation Management

- Tracks token usage via Anthropic API responses
- Automatically summarizes history when approaching 85% of context window
- Keeps last 2 conversation turns verbatim for accurate follow-ups
- Older turns compressed into concise summary

### Security

- SQL validation blocks all data-modifying operations
- Only SELECT queries permitted
- Single table access enforced
- Retry logic (max 3 attempts) for failed queries

### Cost Optimization

- Sonnet 4.5 for complex reasoning (SQL generation)
- Haiku 4.5 for simple formatting (response generation)