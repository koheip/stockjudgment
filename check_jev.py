"""Check Jev connectivity without printing credentials or provider error bodies."""
import os
from main import TypeSafeClient, RetryPolicy


if __name__ == "__main__":
    try:
        with TypeSafeClient(timeout=20, retry=RetryPolicy(max_retries=0)) as client:
            print("Available models:", [model.name for model in client.models.list().models])
            response = client.system_one(model=os.getenv("TYPESAFE_MODEL", "jev-1.13.0").strip() or "jev-1.13.0", state={"value": 1}, questions={
                "check": {"type": "choice", "instructions": "Select the value in state.",
                          "criteria": {"ONE": "value is 1", "OTHER": "value is not 1"}}})
            print("Inference:", response.model, response.choices["check"].choice)
    except Exception as error:
        print("Connection check:", type(error).__name__, "status:", getattr(error, "status", None))
