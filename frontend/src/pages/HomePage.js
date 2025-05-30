import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Typography, Paper, Button, Box, CircularProgress, Alert } from '@mui/material';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import ArticleIcon from '@mui/icons-material/Article';

const HomePage = () => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const onDrop = (acceptedFiles) => {
    // Only accept PDF files
    const pdfFile = acceptedFiles.find(file => file.type === 'application/pdf');
    if (pdfFile) {
      setFile(pdfFile);
      setError('');
    } else {
      setError('Please upload a PDF file');
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    maxFiles: 1
  });

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a resume file');
      return;
    }

    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/upload-resume/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      // Navigate to interview page with session ID
      navigate(`/interview/${response.data.session_id}`);
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || 'Error uploading resume. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ textAlign: 'center', py: 4 }}>
      <Typography variant="h2" component="h1" gutterBottom>
        AI Technical Interview Assistant
      </Typography>
      
      <Typography variant="h5" color="text.secondary" paragraph>
        Upload your resume to start a personalized technical interview
      </Typography>

      <Paper 
        elevation={3} 
        sx={{ 
          maxWidth: 600, 
          mx: 'auto', 
          mt: 4, 
          p: 4,
          backgroundColor: '#ffffff'
        }}
      >
        <Typography variant="h6" gutterBottom>
          Upload Your Resume
        </Typography>

        <div {...getRootProps()} className="dropzone">
          <input {...getInputProps()} />
          <CloudUploadIcon sx={{ fontSize: 48, color: '#3f51b5', mb: 2 }} />
          {isDragActive ? (
            <Typography>Drop your resume here...</Typography>
          ) : (
            <Typography>
              Drag and drop your resume PDF here, or click to select a file
            </Typography>
          )}
        </div>

        {file && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mt: 2 }}>
            <ArticleIcon sx={{ mr: 1, color: '#3f51b5' }} />
            <Typography>{file.name}</Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}

        <Button
          variant="contained"
          color="primary"
          size="large"
          onClick={handleUpload}
          disabled={!file || loading}
          sx={{ mt: 3 }}
          fullWidth
        >
          {loading ? <CircularProgress size={24} color="inherit" /> : 'Start Interview'}
        </Button>
      </Paper>

      <Box sx={{ mt: 6, maxWidth: 800, mx: 'auto' }}>
        <Typography variant="h4" gutterBottom>
          How It Works
        </Typography>
        
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, justifyContent: 'space-between', mt: 3 }}>
          <Paper sx={{ p: 3, flex: 1, m: 1 }}>
            <Typography variant="h6" gutterBottom>1. Upload Resume</Typography>
            <Typography>Upload your resume in PDF format to let our AI analyze your skills and experience.</Typography>
          </Paper>
          
          <Paper sx={{ p: 3, flex: 1, m: 1 }}>
            <Typography variant="h6" gutterBottom>2. Answer Questions</Typography>
            <Typography>Respond to personalized technical questions based on your resume and role.</Typography>
          </Paper>
          
          <Paper sx={{ p: 3, flex: 1, m: 1 }}>
            <Typography variant="h6" gutterBottom>3. Get Feedback</Typography>
            <Typography>Receive detailed feedback and scoring on your technical interview performance.</Typography>
          </Paper>
        </Box>
      </Box>
    </Box>
  );
};

export default HomePage;