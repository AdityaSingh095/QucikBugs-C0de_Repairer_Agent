import os
import sys
import pandas as pd
import matplotlib.pyplot as plt

# Add project root to path so we can import the APR graph
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "Code-Refactoring-QuixBugs"))
sys.path.insert(0, project_root)

from agent_graph import create_apr_graph

# Directory containing QuixBugs Python programs
programs_dir = os.path.join(project_root, "python_programs")

# Initialize the APR workflow graph
apr_app = create_apr_graph()

# Prepare results storage
results = []

for fname in sorted(os.listdir(programs_dir)):
    if not fname.endswith('.py'):
        continue
    file_path = os.path.join(programs_dir, fname)
    print(f"Running APR on {fname}...")

    # Initialize the APR state
    state = {
        'file_path': file_path,
        'original_code': '',
        'current_code': '',
        'error_line_no': 0,
        'patch_line': '',
        'test_output': '',
        'tests_passed': False,
        'attempts': 0,
        'max_attempts': 3,
        'success': False,
        'error_message': '',
        'function_context': {}
    }

    # Invoke the APR agent
    final_state = apr_app.invoke(state)
    results.append({
        'file': fname,
        'success': final_state['success'],
        'attempts': final_state['attempts']
    })

# Create a DataFrame of results
df = pd.DataFrame(results)

# Print summary
print("\nAPR Summary:")
print(df.to_string(index=False))

# Visualization: bar chart of attempts
plt.figure()
plt.bar(df['file'], df['attempts'])
plt.xlabel('QuixBugs File')
plt.ylabel('Number of Attempts')
plt.xticks(rotation=90)
plt.title('APR Attempts per QuixBugs Algorithm')
plt.tight_layout()
plt.show()

# Visualization: pie chart of success vs failure
totals = df['success'].value_counts()
plt.figure()
plt.pie(totals, labels=['Success', 'Failure'], autopct='%1.1f%%')
plt.title('APR Success Rate Across Suite')
plt.show()

# Optionally save results to CSV
output_csv = os.path.join(programs_dir, 'apr_results_summary.csv')
df.to_csv(output_csv, index=False)
print(f"Results saved to {output_csv}")
