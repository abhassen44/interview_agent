import os
import json
from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver
from interview import create_interview_graph, InterviewState
from typing import List, Dict, Any
import re
from langchain_core.messages import HumanMessage
import uuid 
import google.generativeai as genai

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
CONFIG = {"configurable": {"thread_id": str(uuid.uuid4())}}

class InterviewScorecard:
    def __init__(self):
        self.evaluations: List[Dict[str, Any]] = []
        self.current_question = ""
        self.question_counter = 0
    
    def set_current_question(self, question: str):
        """Set the current question being asked"""
        self.current_question = question.strip()
        self.question_counter += 1
        print(f"\n🔍 QUESTION {self.question_counter}:")
        print(f"🤖 INTERVIEWER: {question}")
    
    def evaluate_answer(self, user_answer: str):
        """Evaluate the user's answer using Gemini"""
        if not self.current_question or not user_answer:
            return
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            prompt = f"""
            You are evaluating a technical interview answer. Score out of 10 points total.

            SCORING BREAKDOWN (Total: 10 points):
            - Technical Accuracy: 0-4 points (40%)
            - Depth of Knowledge: 0-3 points (30%) 
            - Communication Clarity: 0-2 points (20%)
            - Practical Application: 0-1 points (10%)

            SCORING SCALE:
            10/10 = Exceptional - Perfect answer with deep insights
            8-9/10 = Excellent - Strong answer with minor gaps
            6-7/10 = Good - Solid understanding with some limitations
            4-5/10 = Fair - Basic understanding but missing key elements
            2-3/10 = Poor - Limited understanding with significant gaps
            0-1/10 = Very Poor - Incorrect or no meaningful content

            Question: {self.current_question}
            Candidate's Answer: {user_answer}

            Provide a JSON response with this exact structure:
            {{
                "score": [integer from 0-10],
                "breakdown": {{
                    "technical_accuracy": [0-4],
                    "depth_knowledge": [0-3],
                    "communication": [0-2],
                    "practical_application": [0-1]
                }},
                "ideal_answer": "[what a perfect 10/10 answer should contain]",
                "feedback": "[specific feedback on strengths and areas for improvement]"
            }}
            
            Be strict but fair. Most answers should be in the 4-8 range unless exceptional or very poor.
            """
            
            response = model.generate_content(prompt)
            evaluation_data = self._parse_evaluation_response(response.text)
            
            if evaluation_data:
                evaluation = {
                    "question_number": self.question_counter,
                    "question": self.current_question,
                    "user_answer": user_answer,
                    "ideal_answer": evaluation_data.get("ideal_answer", ""),
                    "score": evaluation_data.get("score", 0),
                    "breakdown": evaluation_data.get("breakdown", {}),
                    "feedback": evaluation_data.get("feedback", "")
                }
                
                self.evaluations.append(evaluation)
                
                # Show immediate feedback with detailed breakdown
                print(f"\n📊 EVALUATION COMPLETE")
                print(f"⭐ OVERALL SCORE: {evaluation['score']}/10")
                
                # Show breakdown if available
                if evaluation.get('breakdown'):
                    breakdown = evaluation['breakdown']
                    print(f"📈 SCORE BREAKDOWN:")
                    print(f"   🎯 Technical Accuracy: {breakdown.get('technical_accuracy', 0)}/4")
                    print(f"   🧠 Depth of Knowledge: {breakdown.get('depth_knowledge', 0)}/3") 
                    print(f"   💬 Communication: {breakdown.get('communication', 0)}/2")
                    print(f"   🔧 Practical Application: {breakdown.get('practical_application', 0)}/1")
                
                print(f"💡 FEEDBACK: {evaluation['feedback']}")
                print("-" * 50)
                
                return evaluation
            
        except Exception as e:
            print(f"❌ Error evaluating answer: {str(e)}")
            return None
    
    def _parse_evaluation_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response"""
        try:
            # Clean the response text
            cleaned_text = response_text.strip()
            
            # Try to find JSON in the response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_text)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            
            # If no JSON found, try parsing the whole response
            return json.loads(cleaned_text)
            
        except (json.JSONDecodeError, AttributeError):
            # Fallback: extract information using regex
            score_match = re.search(r'"score":\s*(\d+)', response_text)
            feedback_match = re.search(r'"feedback":\s*"([^"]+)"', response_text)
            ideal_match = re.search(r'"ideal_answer":\s*"([^"]+)"', response_text)
            
            if score_match:
                return {
                    "score": int(score_match.group(1)),
                    "feedback": feedback_match.group(1) if feedback_match else "Unable to parse feedback",
                    "ideal_answer": ideal_match.group(1) if ideal_match else "Unable to parse ideal answer"
                }
            
            return {}
    
    def display_final_scorecard(self):
        """Display the complete scorecard at the end"""
        if not self.evaluations:
            print("\n📋 No evaluations recorded.")
            return

        print("\n" + "="*80)
        print("📋 FINAL TECHNICAL INTERVIEW SCORECARD".center(80))
        print("="*80)
        
        total_score = 0
        for eval_data in self.evaluations:
            print(f"\n🔍 QUESTION {eval_data['question_number']}:")
            print(f"❓ Question: {eval_data['question']}")
            print(f"👤 Your Answer: {eval_data['user_answer'][:200]}{'...' if len(eval_data['user_answer']) > 200 else ''}")
            print(f"✅ Ideal Answer: {eval_data['ideal_answer']}")
            print(f"⭐ SCORE: {eval_data['score']}/10")
            
            # Show detailed breakdown if available
            if eval_data.get('breakdown'):
                breakdown = eval_data['breakdown']
                print(f"📊 Score Breakdown:")
                print(f"   🎯 Technical Accuracy: {breakdown.get('technical_accuracy', 0)}/4")
                print(f"   🧠 Depth of Knowledge: {breakdown.get('depth_knowledge', 0)}/3")
                print(f"   💬 Communication: {breakdown.get('communication', 0)}/2") 
                print(f"   🔧 Practical Application: {breakdown.get('practical_application', 0)}/1")
            
            print(f"💡 Feedback: {eval_data['feedback']}")
            print("-" * 80)
            total_score += eval_data['score']
        
        # Calculate final statistics
        avg_score = total_score / len(self.evaluations)
        performance_level = self._get_performance_level(avg_score)
        
        print(f"\n✨ INTERVIEW SUMMARY ✨")
        print(f"📊 Total Questions Answered: {len(self.evaluations)}")
        print(f"🎯 Average Score: {avg_score:.1f}/10.0")
        print(f"🏆 Performance Level: {performance_level}")
        print(f"📈 Total Points Earned: {total_score}/{len(self.evaluations) * 10}")
        print(f"📋 Success Rate: {(avg_score/10)*100:.1f}%")
        print("="*80)
    
    def _get_performance_level(self, avg_score: float) -> str:
        """Determine performance level based on average score"""
        if avg_score >= 9:
            return "🌟 EXCEPTIONAL"
        elif avg_score >= 8:
            return "🔥 EXCELLENT"
        elif avg_score >= 7:
            return "✅ GOOD"
        elif avg_score >= 6:
            return "📈 SATISFACTORY"
        elif avg_score >= 5:
            return "⚠️ NEEDS IMPROVEMENT"
        else:
            return "🔄 REQUIRES SIGNIFICANT WORK"
    
    def save_results(self, filename: str = "interview_scorecard.json"):
        """Save results to JSON file"""
        try:
            results = {
                "interview_summary": {
                    "total_questions": len(self.evaluations),
                    "average_score": sum(e['score'] for e in self.evaluations) / len(self.evaluations) if self.evaluations else 0,
                    "total_points": sum(e['score'] for e in self.evaluations),
                    "max_points": len(self.evaluations) * 10
                },
                "detailed_evaluations": self.evaluations
            }
            
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Scorecard saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving results: {str(e)}")

def is_question(text: str) -> bool:
    """Check if text contains a question"""
    question_markers = ['?', 'what', 'how', 'why', 'when', 'where', 'which', 'explain', 'describe', 'tell me']
    text_lower = text.lower()
    return any(marker in text_lower for marker in question_markers) and len(text.split()) > 5

def main():
    scorecard = InterviewScorecard()
    RESUME_PATH = "abhas_sen.pdf"  # Update with your resume filename
    
    print("🎯 AI TECHNICAL INTERVIEW SYSTEM")
    print("I'll ask technical questions based on your resume and evaluate your answers")
    print("Commands: 'exit' to end, 'scorecard' to view current progress")
    print("=" * 70)

    try:
        with MongoDBSaver.from_conn_string(MONGODB_URI) as checkpointer:
            graph = create_interview_graph(checkpointer=checkpointer)

            # Initialize state
            state: InterviewState = {
                "messages": [HumanMessage(content="Start the technical interview based on the resume")],
                "scorecard": [],
                "current_question": "",
                "resume_path": RESUME_PATH
            }

            # Get the first question
            print("🚀 Starting interview...")
            for event in graph.stream(state, CONFIG, stream_mode="values"):
                if "messages" in event:
                    latest_message = event["messages"][-1]
                    content = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)
                    
                    if is_question(content):
                        scorecard.set_current_question(content)
                        break

            # Main interview loop
            while True:
                try:
                    user_input = input("\n👤 YOUR ANSWER: ").strip()
                    
                    if user_input.lower() in ['exit', 'quit', 'end']:
                        print("\n🏁 INTERVIEW CONCLUDED!")
                        break
                    
                    if user_input.lower() == 'scorecard':
                        scorecard.display_final_scorecard()
                        continue
                    
                    if not user_input:
                        print("⚠️ Please provide an answer or type 'exit' to end.")
                        continue

                    # Evaluate the current answer
                    scorecard.evaluate_answer(user_input)

                    # Get the next question
                    state = {
                        "messages": [HumanMessage(content=f"The candidate answered: {user_input}. Ask the next technical question.")],
                        "scorecard": [],
                        "current_question": "",
                        "resume_path": RESUME_PATH
                    }

                    # Get next question from the graph
                    next_question_found = False
                    for event in graph.stream(state, CONFIG, stream_mode="values"):
                        if "messages" in event:
                            latest_message = event["messages"][-1]
                            content = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)
                            
                            if is_question(content):
                                scorecard.set_current_question(content)
                                next_question_found = True
                                break
                    
                    if not next_question_found:
                        print("\n🎯 Interview completed! All questions have been covered.")
                        break

                except KeyboardInterrupt:
                    print("\n⏹️ Interview interrupted by user")
                    break
                except Exception as e:
                    print(f"\n❌ Error during interview: {str(e)}")
                    print("Continuing with next question...")

    except Exception as e:
        print(f"❌ Error connecting to database: {str(e)}")
        print("Make sure MongoDB is running and accessible")

    finally:
        # Always show final scorecard and save results
        scorecard.display_final_scorecard()
        scorecard.save_results()

if __name__ == "__main__":
    main()