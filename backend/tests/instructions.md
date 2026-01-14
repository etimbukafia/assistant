# Engineering Standard: Python Backend & AI Testing Protocol

This document serves as the mandatory framework for writing and maintaining unit tests. All backend code must adhere to these standards to ensure system stability, rapid refactoring, and AI reliability.

---

## 0. Pre-Testing File Checklist
Before writing a single test for a specific file or module, answer these six questions:

1.  **Is there Business Logic?** If the file only moves data (getters/setters), skip unit testing. If it calculates, transforms, or decides, it requires a test.
2.  **Is it a "Black Box"?** Can I verify inputs and outputs without needing to know the internal loops or private variables?
3.  **What are the "Boundaries"?** What is the smallest, largest, and "nullest" input this file could receive?
4.  **Are there External Dependencies?** Does this file call an API, a Database, or an AI Model? If yes, identify what needs to be **mocked**.
5.  **What is the "Happy Path"?** What does a perfect, error-free execution look like?
6.  **How could this fail?** List at least three failure modes (e.g., Network timeout, malformed JSON, missing dictionary keys).
7. **The "Change" Litmus Test**: Ask yourself: "If I refactor the internals of this function but keep the output the same, will my test break?"
- If Yes: Your test is too coupled to the "lines" and implementation. This is a bad test.
- If No: You are testing the behavior. This is a high-quality unit test.

---

## Part 1: General Backend Testing Principles

### 1. Adherence to F.I.R.S.T. Principles
Every test must be:
* **Fast:** Execution must happen in milliseconds.
* **Independent:** No shared state; tests must be able to run in any order.
* **Repeatable:** Results must be identical regardless of the time of day or environment.
* **Self-Validating:** Clear binary (Pass/Fail) output.
* **Thorough/Timely:** Covers happy paths, edge cases, and security vulnerabilities.

### 2. The AAA (Arrange-Act-Assert) Pattern
Organize test functions into three visual blocks to improve readability:
* **Arrange:** Initialize objects, mock dependencies, and define input data.
* **Act:** Call the specific function or method being tested.
* **Assert:** Verify the result against the expected outcome.

### 3. Isolation via Mocking & Dependency Injection
* **No Side Effects:** Unit tests must never touch the network, disk, or real databases.
* **Tooling:** Use `unittest.mock` or `pytest-mock` to intercept external calls.
* **Design for Testability:** Use Dependency Injection (passing services into constructors) to allow for easy swapping with mocks.

### 4. Respect the Testing Pyramid
Optimize your testing effort based on cost and speed:



[Image of the software testing pyramid]


* **Unit Tests (70%):** High speed, low cost. Focus on logic.
* **Integration Tests (20%):** Verify interactions (e.g., Database + API).
* **End-to-End (10%):** Verify the complete user journey.

### 5. Semantic Naming Conventions
Test names must act as documentation. 
* **Format:** `test_[function]_[scenario]_[expected_result]`
* *Example:* `test_apply_discount_with_expired_coupon_returns_original_price`

### 6. Test Behavior, Not Implementation
* **Black Box Focus:** Test what the code *does*, not how it is written.
* **Refactor-Proof:** If you change an internal `for` loop to a list comprehension, your test should still pass. If it breaks, your test is too "brittle."

### 7. Boundary and Edge Case Coverage
Verify how the system handles the extremes:
* **Nulls/None:** Ensure missing inputs don't trigger unhandled exceptions.
* **Empty Sets:** Test empty strings, lists, and dictionaries.
* **Mathematical Boundaries:** If a threshold is 100, test 99, 100, and 101.

### 8. The "Clean Suite" Rule
* **One Logical Assert:** Each test verifies one specific behavior.
* **No Logic in Tests:** Avoid `if` statements or `for` loops in test code. If a test is complex, it likely needs its own unit test.

---

## Part 2: Scope & Strategy (What to Test)

### 9. Test Public Interfaces & Logic Mazes
* **Every Line? No.** Chasing 100% line coverage leads to "vanity tests" that check trivial code.
* **Every Method? No.** Skip trivial getters, setters, or 3rd-party library internals.
* **The Rule:** Test every **Public Method** and every logical path through **Complex Logic** (conditionals/branching). 
* **"Crucial" Business Logic**: Any code that involves money, security, or data integrity deserves deep testing.
* **Complexity (The Cyclomatic Complexity Rule)**: If a function has many if, else, switch, or try/catch blocks, it has high Cyclomatic Complexity. Every possible path through that "maze" of logic should be tested.

## Part 3: What you should not test
* **Trivial Code**: Don't test "getters" and "setters" (e.g., return self.name). You are testing the Python language at that point, not the app.
* **Third-Party Libraries**: Don't test if SQLAlchemy saves data or if OpenAI returns a string. Assume the library works; test how the code handles what the library returns.
* **Private Methods (Directly)**: If you feel the need to test a _private_method in Python, it usually means that method is doing too much and should be its own public class/utility, or it should be tested implicitly via the public method that calls it.



---

## Part 4: AI-Integrated Application Strategy

### 10. Testing the "Plumbing" (Mocked AI)
AI interactions are non-deterministic. For unit tests:
* **Deterministic Mocks:** Replace AI client calls with mocks that return static, predefined strings or JSON.
* **Parsing Robustness:** Ensure your code handles the AI's response format correctly, especially when using "Structured Outputs."

### 11. AI Evaluations (The "Intelligence" Layer)
Separate from unit tests, maintain an **Eval Suite**:
* **Golden Datasets:** A version-controlled JSON file of inputs and "Ground Truth" answers.
* **Semantic Verification:** Use `cosine similarity` or an `LLM-as-a-judge` (e.g., GPT-4o) to verify contextual accuracy rather than exact string matches.

### 12. Pre-Flight and Post-Flight Robustness
* **Pre-Flight:** Test prompt template generation. Are variables injected correctly? Is PII stripped?
* **Post-Flight:** Test failure modes. Mock AI API timeouts, 429 Rate Limits, and Safety Filter triggers to ensure the backend fails gracefully.

---

## Part 5: Python Implementation Reference

| Requirement | Recommended Python Tooling |
| :--- | :--- |
| **Test Runner** | `pytest` |
| **Mocking** | `pytest-mock` (mocker fixture) |
| **AI API Simulation** | `vcrpy` (Record/Replay real AI responses) |
| **Data Generation** | `faker` or `factory_boy` |
| **Time Manipulation** | `freezegun` |
| **Coverage Analysis** | `pytest-cov` |

```python
# Example of AAA + Mocking + AI Failure Mode
@patch("openai.resources.chat.completions.create")
def test_summarize_fails_gracefully_on_ai_timeout(mock_openai):
    # Arrange
    mock_openai.side_effect = TimeoutError("API Connection Timed Out")
    service = SummarizationService()

    # Act
    result = service.summarize("Long text content")

    # Assert
    assert result["status"] == "error"
    assert "Please try again later" in result["message"]