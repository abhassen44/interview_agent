# AI Technical Interview Agent

This application provides an AI-powered technical interview experience. Upload your resume, answer technical questions, and receive detailed feedback and scoring.

## Features

- Resume analysis to generate personalized technical questions
- Real-time interview with AI interviewer
- Detailed evaluation and feedback on answers
- Comprehensive scorecard with overall performance metrics

## Project Structure

```
├── api.py                # FastAPI backend
├── interview.py          # Interview logic and LangGraph workflow
├── main.py               # CLI version of the interview agent
├── resume.py             # Resume parsing and analysis
├── run_api.py            # Script to run the FastAPI server
├── frontend/             # React frontend application
│   ├── public/           # Static assets
│   └── src/              # React components and logic
```

## Prerequisites

- Python 3.9+
- Node.js 14+
- MongoDB (for LangGraph checkpointing)
- Qdrant (for vector storage)

## Setup

### Backend Setup

1. Create a virtual environment and activate it:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# OR
source .venv/bin/activate  # Linux/Mac
```

2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with the following variables:

```
GOOGLE_API_KEY=your_google_api_key
MONGODB_URI=mongodb://localhost:27017/
```

4. Start the Qdrant server (if not already running):

```bash
docker run -p 6333:6333 qdrant/qdrant
```

5. Run the FastAPI server:

```bash
python run_api.py
```

### Frontend Setup

1. Navigate to the frontend directory:

```bash
cd frontend
```

2. Install the required Node.js packages:

```bash
npm install
```

3. Start the React development server:

```bash
npm start
```

## Usage

1. Open your browser and navigate to `http://localhost:3000`
2. Upload your resume (PDF format)
3. Answer the technical questions provided by the AI interviewer
4. Receive feedback and evaluation for each answer
5. View your final scorecard with detailed performance metrics

## API Endpoints

- `POST /upload-resume/`: Upload a resume to start an interview session
- `GET /start-interview/{session_id}`: Start the interview and get the first question
- `POST /submit-answer/`: Submit an answer and get the next question or evaluation
- `GET /scorecard/{session_id}`: Get the current scorecard for a session
- `POST /end-interview/{session_id}`: End the interview session and finalize the scorecard
- `DELETE /session/{session_id}`: Delete a session and its associated files
- `WebSocket /ws/{session_id}`: Real-time interview communication

## License

MIT