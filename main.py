"""Main entry point for the customer request agent"""
import json
import sys

from dotenv import load_dotenv

from src.database.json_db import JsonLocalDatabase
from src.llm.client import OpenAILLMClient
from src.agent import CustomerRequestAgent
from src.logging.logger import setup_logger

load_dotenv()


def main():
    """Main execution"""
    setup_logger()

    try:
        db = JsonLocalDatabase()
        llm = OpenAILLMClient()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    agent = CustomerRequestAgent(llm, db)

    sample_requests_file = "data/sample_requests.json"
    with open(sample_requests_file, "r") as f:
        requests = json.load(f)

    print("\n" + "=" * 80)
    print("CUSTOMER REQUEST AGENT - PROCESSING SAMPLE REQUESTS")
    print("=" * 80 + "\n")

    for request in requests:
        request_id = request["request_id"]
        text = request["text"]
        expected = request["expected_action"]

        decision = agent.process_request(request_id, text)

        print(f"Request ID: {request_id}")
        print(f"Text: {text[:60]}..." if len(text) > 60 else f"Text: {text}")
        print(f"Expected: {expected}")
        print(f"Decision: {decision.action}")
        print(f"Reasoning: {decision.reasoning_trace}")
        print(f"Match: {'✅' if decision.action == expected else '❌'}")
        print("-" * 80)


if __name__ == "__main__":
    main()
