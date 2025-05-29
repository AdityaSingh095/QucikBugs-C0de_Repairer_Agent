# 🧠 Automated Code Correction using LLMs

## 📍 Overview

This project was built as part of Round 2 of the AIMS-DTU Research Internship selection task. It aims to automatically detect and correct **single-line defects** in Python programs using a **prompt-driven language model agent**. The agent analyzes buggy implementations from the **QuixBugs** dataset and proposes minimal code edits that preserve the logic of classic algorithms while making the code pass its test cases.

The solution utilizes:

* **Prompt templates** customized for code repair
* **LangGraph** for orchestrating agent workflows
* **Google Gemini API** to generate fixes
* **Test-driven validation** to verify the correctness of patches

---

## 📁 Repository Structure

```
.
├── agent_graph.py              # Main agent code with LangGraph logic
├── tools.py                    # Code manipulation utilities
├── result.py                   # Test harness executor for evaluation
├── Code-Refactoring-QuixBugs/  #Contains all Quicbugs Files
├── README.md                   # Project documentation
└── requirements.txt            # Optional: environment dependencies
```

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/AdityaSingh095/QucikBugs-C0de_Repairer_Agent
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Add Gemini API Key

Set up your API key as an environment variable:

```bash
export GEMINI_API_KEY="your-key-here"
```

Or use a `.env` file and load it with `dotenv` if supported.

---

## 🚀 How to Use

### 🔁 Run Agent on All Files

```bash
python agent_graph.py --all
```

### 🧪 Validate Patched Programs

```bash
python result.py
```

This executes the test harness (`tester.py`) against all files in `python_programs/` and prints the pass/fail result.

### 🛠 Repair a Single File

```bash
python agent_graph.py INSERT_FILE_NAME.py
```

---

## 🛠 Methodology

1. **Bug Detection:**

   * Each file is tested using `tester.py`. If it fails, the error trace is parsed to identify the buggy line.

2. **Prompt Construction:**

   * A custom prompt template is populated with:

     * Function name
     * Buggy line
     * Full context of the function
     * Error message and test output

3. **Fix Generation:**

   * The Gemini model (gemini-1.5-flash) is queried using LangGraph’s prompt node. Only the fixed line is expected as output.

4. **Patch Application:**

   * The faulty line is replaced using `apply_fix()` from `tools.py`.

5. **Test Validation:**

   * `RunTestsTool` reruns the test harness to check correctness. If still failing, a retry mechanism (up to 5 attempts) kicks in.

---

## 💡 Highlights

* **Zero-Shot Repair:** No model training required. Uses prompt-only learning.
* **14 Defect Types Covered:** Off-by-one, incorrect loop bounds, wrong operators, etc.
* **Fully Automated Workflow:** Just run and get fixed files.
* **Readable Fixes:** Fixes are traceable and human-interpretable.

---

## 📊 Evaluation

* Total files tested: 40
* Files successfully fixed: 29
* Human benchmark: 40/40 (from `correct_python_programs/`)
* All fixes verified using original test harness

---

## 🔍 Future Work

* Extend support to **multi-line defect repair**
* Adapt system for **Java programs** in QuixBugs
* Add **explanatory reasoning** with each fix
* Explore **active learning loop** based on failed test feedback

---


