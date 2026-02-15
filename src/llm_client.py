from anthropic import Anthropic
from dotenv import load_dotenv
import os
load_dotenv()

class LLMClient:
    def __init__(self):
        if os.getenv("ANTHROPIC_API_KEY") is None:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def generate_response_usage(self, model, prompt, max_tokens) -> tuple[str, int]:
        response = self.client.messages.create(
            max_tokens=max_tokens,
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text, response.usage.output_tokens

    def count_tokens(self, model, prompt) -> int:
        tokens =self.client.messages.count_tokens(model=model, messages=[{"role": "user", "content": prompt}])
        return tokens.input_tokens