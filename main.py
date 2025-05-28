import os
from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver
from interview import create_interview_graph
from langchain_core.messages import HumanMessage

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
CONFIG = {"configurable": {"thread_id": "interview_session_1"}}
MAX_QUESTIONS = 10

def get_resume_file():
    """Get resume file path from user."""
    while True:
        resume_path = input("📄 Please enter the path to the resume PDF file: ").strip()
        if os.path.exists(resume_path) and resume_path.lower().endswith('.pdf'):
            return resume_path
        else:
            print("❌ File not found or not a PDF. Please try again.")

def main():
    print("🎯 AI Interview Agent - Resume-Based Interview System")
    print("="*60)
    
    # Get resume file
    resume_file = get_resume_file()
    print(f"✅ Resume loaded: {os.path.basename(resume_file)}")
    
    with MongoDBSaver.from_conn_string(MONGODB_URI) as checkpointer:
        graph = create_interview_graph(checkpointer=checkpointer)
        
        print(f"\n🚀 Interview Session Started!")
        print(f"📋 Maximum Questions: {MAX_QUESTIONS}")
        print(f"📊 You'll receive a detailed scorecard at the end")
        print(f"💡 Type 'exit' or 'quit' to end early\n")
        
        # Initialize the interview with resume information
        initial_state = {
            "messages": [HumanMessage(content=f"Please start the interview. Resume file: {resume_file}")],
            "question_count": 0,
            "max_questions": MAX_QUESTIONS,
            "interview_concluded": False,
            "candidate_responses": [],
            "current_phase": "resume_based",
            "identified_role": "",
            "resume_file_path": resume_file,
            "question_scores": []
        }
        
        # Start the interview
        try:
            print("🤖 AI Interviewer: Starting interview analysis...")
            for event in graph.stream(initial_state, CONFIG, stream_mode="values"):
                if "messages" in event and event["messages"]:
                    latest_msg = event["messages"][-1]
                    content = getattr(latest_msg, "content", str(latest_msg))
                    if content and not content.startswith("Please start"):
                        print(f"\n🤖 AI Interviewer: {content}")
                        break
        except Exception as e:
            print(f"❌ Error starting interview: {e}")
            return
        
        # Main interview loop
        question_count = 0
        interview_concluded = False
        
        while question_count < MAX_QUESTIONS and not interview_concluded:
            try:
                # Get user input
                user_input = input(f"\n👤 You: ").strip()
                
                if user_input.lower() in ["exit", "quit"]:
                    print("\n🔚 Interview ended by user.")
                    interview_concluded = True
                    break
                
                if not user_input:
                    print("Please provide an answer.")
                    continue
                
                # Process user response
                current_state = {
                    "messages": [HumanMessage(content=user_input)],
                    "question_count": question_count,
                    "max_questions": MAX_QUESTIONS,
                    "interview_concluded": False,
                    "resume_file_path": resume_file
                }
                
                # Get AI response
                ai_responded = False
                for event in graph.stream(current_state, CONFIG, stream_mode="values"):
                    # Track question count
                    if "question_count" in event:
                        question_count = event["question_count"]
                    
                    # Check if interview concluded
                    if "interview_concluded" in event:
                        interview_concluded = event["interview_concluded"]
                    
                    # Display AI messages
                    if "messages" in event and event["messages"]:
                        latest_msg = event["messages"][-1]
                        content = getattr(latest_msg, "content", str(latest_msg))
                        
                        # Skip echoing user input
                        if hasattr(latest_msg, "type") and latest_msg.type == "human":
                            continue
                            
                        if content and content != user_input:
                            print(f"\n🤖 AI Interviewer: {content}")
                            ai_responded = True
                            
                            # Check if this is a question
                            if "?" in content and not content.lower().startswith("here"):
                                question_count += 1
                                print(f"📊 Progress: {question_count}/{MAX_QUESTIONS} questions")
                
                if not ai_responded:
                    print("🤖 AI Interviewer: Thank you for your response.")
                
                # Check if we've reached the limit
                if question_count >= MAX_QUESTIONS:
                    interview_concluded = True
                    
            except Exception as e:
                print(f"❌ Error during interview: {e}")
                continue
        
        # Generate final scorecard
        print(f"\n{'='*60}")
        print("📋 GENERATING FINAL SCORECARD...")
        print("="*60)
        
        try:
            scorecard_state = {
                "messages": [HumanMessage(content="generate_final_scorecard")],
                "question_count": question_count,
                "max_questions": MAX_QUESTIONS,
                "interview_concluded": True,
                "resume_file_path": resume_file
            }
            
            scorecard_generated = False
            for event in graph.stream(scorecard_state, CONFIG, stream_mode="values"):
                if "messages" in event and event["messages"]:
                    latest_msg = event["messages"][-1]
                    content = getattr(latest_msg, "content", str(latest_msg))
                    
                    if ("scorecard" in content.lower() or 
                        "score:" in content.lower() or 
                        "performance" in content.lower()):
                        print(content)
                        scorecard_generated = True
            
            if not scorecard_generated:
                # Fallback scorecard
                print(f"""
🎯 INTERVIEW SUMMARY
{'='*40}
📊 Questions Completed: {question_count}/{MAX_QUESTIONS}
📈 Completion Rate: {(question_count/MAX_QUESTIONS)*100:.1f}%
🎪 Status: {'Completed' if question_count >= MAX_QUESTIONS else 'Ended Early'}

Thank you for participating in the interview!
                """)
                
        except Exception as e:
            print(f"❌ Error generating scorecard: {e}")
            print(f"""
📊 BASIC INTERVIEW SUMMARY
Questions Answered: {question_count}/{MAX_QUESTIONS}
Status: Interview Completed
            """)
        
        print(f"\n🎉 Interview session ended. Thank you!")

if __name__ == "__main__":
    main()