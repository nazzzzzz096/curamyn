# Testing Strategy – Curamyn

This document describes the testing philosophy and strategy used in the Curamyn AI system.

Curamyn is a multimodal AI application integrating:
- Large Language Models (LLMs)
- Voice (Speech-to-Text and Text-to-Speech)
- Computer Vision (CNN-based medical image analysis)
- Safety-guarded healthcare logic

Due to the non-deterministic and resource-heavy nature of these components, a structured and defensive testing strategy is used.

---

## 1. Testing Philosophy

Curamyn follows the principle:

**“Test system behavior, not model intelligence.”**

The goal is to verify that:
- The system responds safely
- Failures are handled gracefully
- Incorrect inputs never crash the system
- External services are isolated from core logic

Model accuracy and human-level understanding are evaluated separately from software tests.

---

## 2. Types of Tests

### Unit Tests
- Validate individual service behavior
- No external calls (LLM, Whisper, CNN, S3)
- Use mocking for deterministic outcomes

Examples:
- LLM fallback handling
- Safety rule enforcement
- Voice pipeline control flow
- Image routing logic

Location:
  tests/unit/


---

### Integration Tests
- Validate interaction between internal components
- Authentication is mocked
- External services remain isolated

Example:
- `/ai/interact` endpoint behavior with mocked user authentication

Location:
 tests/integration/


---

### End-to-End (E2E) Tests
- Smoke tests only
- Validate that the application boots and responds
- No real AI inference

Location:
 tests/e2e/


---

## 3. AI-Specific Testing Strategy

### Why LLM Outputs Are Not Asserted Directly

LLM responses can vary due to:
- Token limits
- Provider behavior
- Internal model reasoning
- Network or API failures

Because of this, tests **do not** assert exact LLM output text.

Instead, tests validate:
- Presence of a response
- Correct structure of responses
- Execution of fallback logic when LLM output is unusable

This reflects real-world production conditions.

---

## 4. Fallback-First Validation

Fallback behavior is treated as **first-class functionality**.

LLM failure scenarios are considered expected and safe paths, including:
- Empty responses
- Truncated responses
- Invalid structured output

Tests explicitly validate that:
- Safe fallback responses are returned
- The system never crashes due to AI failure
- User experience degrades gracefully

---

## 5. Mocking Strategy

All external and resource-heavy dependencies are mocked:
- LLM APIs
- Speech-to-Text (Whisper)
- Text-to-Speech engines
- CNN inference models
- S3 model loading

Mocking is applied **at the usage point**, ensuring:
- Deterministic test results
- No API costs
- CI/CD compatibility
- Fast local execution

This is why pytest does not require real audio files or real images.

---

## 6. What Is Intentionally NOT Tested

The following are intentionally excluded from pytest:
- Model accuracy or medical correctness
- Audio quality or speech naturalness
- Image classification performance
- LLM intelligence or creativity

These aspects are evaluated through:
- Offline model benchmarking
- Dataset-based evaluation
- Manual testing and demos

This separation ensures clear boundaries between **software testing** and **model validation**.

---

## 7. How to Run Tests

Run all tests:
```bash
pytest

Run specific modules:

  pytest tests/unit/llm
  pytest tests/unit/voice
  pytest tests/unit/vision
