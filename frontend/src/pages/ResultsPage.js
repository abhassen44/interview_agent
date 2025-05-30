import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Typography, 
  Paper, 
  Button, 
  Box, 
  CircularProgress, 
  Alert,
  Card,
  CardContent,
  Divider,
  Rating,
  List,
  ListItem,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import axios from 'axios';

const ResultsPage = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [scorecard, setScorecard] = useState(null);

  useEffect(() => {
    const fetchScorecard = async () => {
      try {
        const response = await axios.get(`/scorecard/${sessionId}`);
        setScorecard(response.data);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching scorecard:', err);
        setError(err.response?.data?.detail || 'Error fetching results. Please try again.');
        setLoading(false);
      }
    };

    fetchScorecard();
  }, [sessionId]);

  const handleStartNew = () => {
    navigate('/');
  };

  const handleDeleteSession = async () => {
    try {
      await axios.delete(`/session/${sessionId}`);
      navigate('/');
    } catch (err) {
      console.error('Error deleting session:', err);
      setError(err.response?.data?.detail || 'Error deleting session. Please try again.');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading your results...</Typography>
      </Box>
    );
  }

  if (!scorecard) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || 'No scorecard found for this session.'}
        </Alert>
        <Button variant="contained" onClick={handleStartNew}>
          Start New Interview
        </Button>
      </Box>
    );
  }

  return (
    <Box className="scorecard-container">
      <Typography variant="h4" gutterBottom>
        Interview Results
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ my: 2 }}>
          {error}
        </Alert>
      )}

      <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
        <Typography variant="h5" gutterBottom>
          Role: {scorecard.role}
        </Typography>
        
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', my: 3 }}>
          <Box sx={{ 
            width: 120, 
            height: 120, 
            borderRadius: '50%', 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center',
            backgroundColor: '#f0f7ff',
            border: '4px solid #3f51b5'
          }}>
            <Typography className="overall-score">
              {scorecard.overall_score}/10
            </Typography>
          </Box>
        </Box>
        
        <Typography variant="subtitle1" align="center" gutterBottom>
          Overall Performance
        </Typography>
        
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
          <Rating 
            value={scorecard.overall_score / 2} 
            precision={0.5} 
            readOnly 
            size="large"
            max={5}
          />
        </Box>
        
        <Typography variant="body2" align="center" color="text.secondary">
          Based on {scorecard.total_questions} questions
        </Typography>
      </Paper>

      <Typography variant="h5" gutterBottom>
        Detailed Evaluation
      </Typography>

      {scorecard.evaluations.map((index) => (
        <Accordion key={index} sx={{ mb: 2 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
              <Typography variant="subtitle1">
                Question {index + 1}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Rating value={eval.score / 2} precision={0.5} readOnly size="small" />
                <Typography variant="body2" sx={{ ml: 1 }}>
                  {eval.score}/10
                </Typography>
              </Box>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="subtitle2" gutterBottom>
              Question:
            </Typography>
            <Typography variant="body2" paragraph>
              {eval.question}
            </Typography>
            
            <Divider sx={{ my: 1 }} />
            
            <Typography variant="subtitle2" gutterBottom>
              Your Answer:
            </Typography>
            <Typography variant="body2" paragraph>
              {eval.human_answer}
            </Typography>
            
            <Typography variant="subtitle2" gutterBottom>
              Ideal Answer:
            </Typography>
            <Typography variant="body2" paragraph>
              {eval.llm_actual_answer}
            </Typography>
            
            <Box className="feedback">
              <Typography variant="subtitle2" gutterBottom>
                Feedback:
              </Typography>
              <Typography variant="body2">
                {eval.reason}
              </Typography>
            </Box>
          </AccordionDetails>
        </Accordion>
      ))}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
        <Button
          variant="outlined"
          color="secondary"
          onClick={handleDeleteSession}
        >
          Delete Session
        </Button>
        
        <Button
          variant="contained"
          color="primary"
          onClick={handleStartNew}
        >
          Start New Interview
        </Button>
      </Box>
    </Box>
  );
};

export default ResultsPage;