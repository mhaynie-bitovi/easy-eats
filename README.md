# Temporal Workshop

A Temporal workflow application for order management.

## Prerequisites

- Python 3.12+
- A running [Temporal](https://temporal.io/) server (for running workflows)

## Development Setup

1. Clone the repo and `cd` into it:

   ```sh
   git clone <repo-url>
   cd temporal-workshop
   ```

2. Create and activate a virtual environment:

   ```sh
   python3 -m venv env
   source env/bin/activate
   ```

3. Install dependencies and the project in editable mode:

   ```sh
   pip install -r requirements.txt
   pip install -e .
   ```

4. Run the tests:

   ```sh
   pytest
   ```