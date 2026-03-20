---
name: benchmark
description: Run the Prompt Master benchmark suite to evaluate prompt optimization quality and suggest improvements based on results.
user-invocable: true
allowed-tools: Bash, Read, Grep
---

# Run Benchmarks

Run the Prompt Master benchmark suite to evaluate prompt optimization quality. Analyze the results and suggest improvements.

## Process

1. Run the benchmark command:
   ```bash
   prompt-master benchmark --no-api
   ```

2. If the user has an API key set and wants AI-powered benchmarks:
   ```bash
   prompt-master benchmark
   ```

3. For LLM-as-judge evaluation (most thorough):
   ```bash
   prompt-master benchmark --judge
   ```

4. To benchmark a specific domain:
   ```bash
   prompt-master benchmark -d workflow --no-api
   ```

5. To save results for comparison:
   ```bash
   prompt-master benchmark --no-api --save --tag <label>
   ```

## After running

Analyze the output:
- **Structural score < 70%**: Significant issues — identify which checks are failing and why
- **Structural score 70-85%**: Acceptable for template mode; look for easy wins in keyword coverage
- **Structural score > 85%**: Good — focus on the remaining failures
- **Judge score < 3.0/5.0**: Prompt quality needs work
- **Judge score > 4.0/5.0**: Excellent

Common failure patterns:
- `FAIL section:X` → The template or optimizer isn't generating the expected markdown section headers
- `FAIL keyword:X` → Domain-relevant terms are missing from the output
- `FAIL specificity` → Vague filler phrases are present in the output
- `FAIL structure` → Missing markdown formatting (headers + lists/bold)

Suggest specific code changes in `optimizer.py`, `fallback.py`, or `templates/` to fix failures.
