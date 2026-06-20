"""Evaluation script to test agent decisions"""
import json
import sys

from dotenv import load_dotenv

from src.database.json_db import JsonLocalDatabase
from src.llm.client import OpenAILLMClient
from src.agent import CustomerRequestAgent
from src.logging.logger import setup_logger

load_dotenv()


def evaluate():
    """Run evaluation against sample requests"""
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
    print("EVALUATION REPORT")
    print("=" * 80 + "\n")

    passed = 0
    failed = 0
    results = []

    for request in requests:
        request_id = request["request_id"]
        text = request["text"]
        expected_action = request["expected_action"]

        decision = agent.process_request(request_id, text)
        actual_action = decision.action

        is_correct = actual_action == expected_action
        if is_correct:
            passed += 1
            status = "✅ PASS"
        else:
            failed += 1
            status = "❌ FAIL"

        results.append(
            {
                "request_id": request_id,
                "expected": expected_action,
                "actual": actual_action,
                "status": status,
            }
        )

    # Print results
    for result in results:
        print(f"{result['status']}: {result['request_id']}")
        print(f"  Expected: {result['expected']}, Got: {result['actual']}")

    print("\n" + "=" * 80)
    total = passed + failed
    accuracy = (passed / total * 100) if total > 0 else 0
    print(f"FINAL ACCURACY: {accuracy:.1f}% ({passed}/{total} tests passed)")
    print("=" * 80 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(evaluate())
