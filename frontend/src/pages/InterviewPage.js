import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Typography, 
  Paper, 
  TextField, 
  Button, 
  Box, 
  CircularProgress, 
  Alert,
  Card,
  CardContent,
  Divider,
  Rating
} from '@mui/material';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';

const InterviewPage = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  const [startingInterview, setStartingInterview] = useState(true);
  const [error, setError] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [evaluation, setEvaluation] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);
  const [websocket, setWebsocket] = useState(null);
  const [connected, setConnected] = useState(false);

  // Initialize WebSocket connection
  useEffect(() => {
    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/${sessionId}`;
    
    // For development with React's dev server proxy
    const devWsUrl = `ws://localhost:8000/ws/${sessionId}`;
    
    const ws = new WebSocket(process.env.NODE_ENV === 'production' ? wsUrl : devWsUrl);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.error) {
        setError(data.error);
        setLoading(false);
        return;
      }
      
      if (data.type === 'question') {
        setQuestion(data.content);
        setQuestionCount(prev => prev + 1);
        setLoading(false);
        setStartingInterview(false);
      }
      
      if (data.type === 'evaluation') {
        setEvaluation(data.content);
        setSubmitting(false);
      }
      
      if (data.type === 'end') {
        navigate(`/results/${sessionId}`);
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('Connection error. Please refresh the page.');
      setLoading(false);
    };
    
    setWebsocket(ws);
    
    // Cleanup on unmount
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [sessionId, navigate]);

  // Fallback to REST API if WebSocket fails
  useEffect(() => {
    const fetchFirstQuestion = async () => {
      if (!connected && startingInterview) {
        try {
          const response = await axios.get(`/start-interview/${sessionId}`);
          setQuestion(response.data.question);
          setQuestionCount(1);
          setLoading(false);
          setStartingInterview(false);
        } catch (err) {
          console.error('Error starting interview:', err);
          setError(err.response?.data?.detail || 'Error starting interview. Please try again.');
          setLoading(false);
        }
      }
    };

    // Wait a bit to see if WebSocket connects
    const timer = setTimeout(() => {
      if (!connected && startingInterview) {
        fetchFirstQuestion();
      }
    }, 3000);

    return () => clearTimeout(timer);
  }, [sessionId, connected, startingInterview]);

  const handleSubmitAnswer = async () => {
    if (!answer.trim()) {
      setError('Please provide an answer');
      return;
    }

    setSubmitting(true);
    setError('');

    // Try WebSocket first
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({
        type: 'answer',
        content: answer
      }));
    } else {
      // Fallback to REST API
      try {
        const response = await axios.post('/submit-answer/', {
          session_id: sessionId,
          answer: answer
        });

        if (response.data.evaluation) {
          setEvaluation(response.data.evaluation);
        }

        setQuestion(response.data.question);
        setQuestionCount(prev => prev + 1);
        setSubmitting(false);
      } catch (err) {
        console.error('Error submitting answer:', err);
        setError(err.response?.data?.detail || 'Error submitting answer. Please try again.');
        setSubmitting(false);
      }
    }

    // Clear the answer field
    setAnswer('');
  };

  const handleEndInterview = async () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({
        type: 'end'
      }));
    } else {
      try {
        await axios.post(`/end-interview/${sessionId}`);
        navigate(`/results/${sessionId}`);
      } catch (err) {
        console.error('Error ending interview:', err);
        setError(err.response?.data?.detail || 'Error ending interview. Please try again.');
      }
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Preparing your interview...</Typography>
      </Box>
    );
  }

  return (
    <Box className="interview-container">
      <Typography variant="h4" gutterBottom>
        Technical Interview
      </Typography>
      
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Question {questionCount} - Answer thoroughly to demonstrate your knowledge
      </Typography>

      {error && (
        <Alert severity="error" sx={{ my: 2 }}>
          {error}
        </Alert>
      )}

      <Card className="question-card" variant="outlined">
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Interviewer Question:
          </Typography>
          <Typography variant="body1">
            <ReactMarkdown>{question}</ReactMarkdown>
          </Typography>
        </CardContent>
      </Card>

      {evaluation && (
        <Card className="evaluation-card" variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Evaluation of Previous Answer
            </Typography>
            
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Typography variant="body1" sx={{ mr: 1 }}>
                Score:
              </Typography>
              <Rating 
                value={evaluation.score / 2} 
                precision={0.5} 
                readOnly 
                max={5}
              />
              <Typography variant="body1" sx={{ ml: 1 }}>
                {evaluation.score}/10
              </Typography>
            </Box>
            
            <Divider sx={{ my: 1 }} />
            
            <Typography variant="subtitle2" gutterBottom>
              Ideal Answer:
            </Typography>
            <Typography variant="body2" paragraph>
              {evaluation.llm_actual_answer}
            </Typography>
            
            <Typography variant="subtitle2" gutterBottom>
              Feedback:
            </Typography>
            <Typography variant="body2">
              {evaluation.reason}
            </Typography>
          </CardContent>
        </Card>
      )}

      <Box sx={{ mt: 3 }}>
        <TextField
          label="Your Answer"
          multiline
          rows={6}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          variant="outlined"
          fullWidth
          className="answer-input"
          disabled={submitting}
        />

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
          <Button
            variant="outlined"
            color="secondary"
            onClick={handleEndInterview}
            disabled={submitting}
          >
            End Interview
          </Button>
          
          <Button
            variant="contained"
            color="primary"
            onClick={handleSubmitAnswer}
            disabled={submitting}
          >
            {submitting ? <CircularProgress size={24} color="inherit" /> : 'Submit Answer'}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default InterviewPage;