import os
import json
from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver
from interview import create_interview_graph, InterviewState
from typing import List, Dict, Any
import re
from langchain_core.messages import HumanMessage
import uuid 

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
CONFIG = {"configurable": {"thread_id": str(uuid.uuid4())}}

class Scorecard:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.current_question = ""
    
    def add_evaluation(self, evaluation: Dict[str, Any]) -> bool:
        required_keys = {'question', 'human_answer', 'llm_actual_answer', 'score', 'reason'}
        if all(key in evaluation for key in required_keys):
            self.results.append(evaluation)
            return True
        return False
    
    def display(self):
        if not self.results:
            print("\n📋 Scorecard is empty. No evaluations yet.")
            return

        print("\n" + "="*70)
        print("📋 TECHNICAL INTERVIEW SCORECARD".center(70))
        print("="*70)
        
        total_score = 0
        for i, eval in enumerate(self.results, 1):
            print(f"\n🔍 QUESTION {i}:")
            print(f"   💬 {eval['question']}")
            print(f"   👤 YOUR ANSWER: {eval['human_answer']}")
            print(f"   ✅ IDEAL ANSWER: {eval['llm_actual_answer']}")
            print(f"   ⭐ SCORE: {eval['score']}/10")
            print(f"   📝 FEEDBACK: {eval['reason']}")
            print("-"*70)
            total_score += eval['score']
        
        avg_score = total_score / len(self.results)
        print(f"\n✨ OVERALL SCORE: {avg_score:.1f}/10 ✨")
        print("="*70)

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Robust JSON extraction from LLM response text"""
    try:
        # Try to parse as pure JSON first
        return json.loads(text)
    except json.JSONDecodeError:
        # Extract JSON substring if embedded in text
        try:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except:
            return {}
    return {}

def main():
    scorecard = Scorecard()
    RESUME_PATH = "abhas_sen.pdf"  # Use your resume filename
    
    with MongoDBSaver.from_conn_string(MONGODB_URI) as checkpointer:
        graph = create_interview_graph(checkpointer=checkpointer)

        # Initialize state
        state: InterviewState = {
            "messages": [
                HumanMessage(content="Start the technical interview")
            ],
            "scorecard": [],
            "current_question": "",
            "resume_path": RESUME_PATH
        }

        print("🎯 AI TECHNICAL INTERVIEW SYSTEM")
        print("I'll ask technical questions and evaluate your answers")
        print("Type 'exit' to end or 'scorecard' to view progress")
        print("-" * 70)

        # Get first question
        for event in graph.stream(state, CONFIG, stream_mode="values"):
            if "messages" in event:
                for msg in event["messages"]:
                    content = msg.content if hasattr(msg, 'content') else str(msg)
                    print(f"\n🤖 INTERVIEWER: {content}")
                    if "?" in content:
                        scorecard.current_question = content

        # Main interview loop
        while True:
            try:
                user_input = input("\n👤 YOUR ANSWER: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("\n🏁 INTERVIEW CONCLUDED!")
                    scorecard.display()
                    with open("interview_results.json", "w") as f:
                        json.dump(scorecard.results, f, indent=2)
                    print("💾 Results saved to interview_results.json")
                    break
                
                if user_input.lower() == 'scorecard':
                    scorecard.display()
                    continue

                # Update state with user response
                state = {
                    "messages": [HumanMessage(content=user_input)],
                    "scorecard": scorecard.results,
                    "current_question": scorecard.current_question,
                    "resume_path": RESUME_PATH
                }

                # Process through LangGraph
                full_response = ""
                for event in graph.stream(state, CONFIG, stream_mode="values"):
                    if "messages" in event:
                        for msg in event["messages"]:
                            content = msg.content if hasattr(msg, 'content') else str(msg)
                            full_response += content + "\n"
                            
                            # Detect new questions
                            if "?" in content and len(content.split()) > 5:
                                scorecard.current_question = content
                                print(f"\n🤖 INTERVIEWER: {content}")
                            
                            # Try to parse evaluation
                            json_data = extract_json_from_text(content)
                            if json_data and "SCORE" in json_data:
                                evaluation = {
                                    "question": json_data.get("question", scorecard.current_question),
                                    "human_answer": user_input,
                                    "llm_actual_answer": json_data.get("ACTUAL_ANSWER", ""),
                                    "score": int(json_data["SCORE"]),
                                    "reason": json_data.get("REASON", "")
                                }
                                if scorecard.add_evaluation(evaluation):
                                    print(f"\n📊 EVALUATION: Score {evaluation['score']}/10")
                                    print(f"💡 FEEDBACK: {evaluation['reason']}")

                # Print any remaining response text
                if full_response and not full_response.startswith("{"):
                    print(f"\n🤖 INTERVIEWER: {full_response}")

            except KeyboardInterrupt:
                print("\n⏹️ Session interrupted")
                break
            except Exception as e:
                print(f"\n❌ ERROR: {str(e)}")

if __name__ == "__main__":
    main()