# Dashboard FastAPI Server

## Setup

1. **Clone the repository** (if not already done):

   ```sh
   git clone <repo-url>
   cd dashboard
   ```

2. **Create and activate a virtual environment:**

   On Windows:
   ```sh
   python -m venv venv
   venv\Scripts\activate
   ```

   On macOS/Linux:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```sh
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**

   - Create a `.env` file.
   - Make sure `AZURE_PAT` is set in `.env`.

## Running the FastAPI Server

```sh
uvicorn main:app --reload
```

- The server will be available at: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to view all API docs

