import os
import uuid
from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver
from interview import create_interview_graph

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
PDF_PATH = os.getenv("PDF_PATH", "abhas_sen.pdf")

# Generate a unique thread ID for each session
thread_id = str(uuid.uuid4())
CONFIG = {
    "configurable": {
        "thread_id": thread_id,
        "pdf_path": PDF_PATH
    }
}

def main():
    with MongoDBSaver.from_conn_string(MONGODB_URI) as checkpointer:
        graph = create_interview_graph(checkpointer=checkpointer)

        print("\n🧠 Interview Agent initialized. Beginning interview...\n")

        question_count = 0
        max_questions = 10
        interview_done = False
        total_score = 0
        feedback_list = []

        while question_count < max_questions and not interview_done:
            try:
                response_text = ""
                for event in graph.stream(
                    {"messages": []}, CONFIG, stream_mode="values"
                ):
                    if "messages" in event:
                        for msg in event["messages"]:
                            content = getattr(msg, "content", str(msg))
                            print("AI:", content)

                            user_input = input("You: ").strip()
                            if user_input.lower() in ["exit", "quit"]:
                                interview_done = True
                                break

                            response = graph.invoke({
                                "messages": [
                                    {"role": "user", "content": user_input}
                                ]
                            }, CONFIG)

                            score = response.get("score", 0)
                            feedback = response.get("feedback", "No feedback provided.")

                            total_score += score
                            feedback_list.append((user_input, score, feedback))
                            question_count += 1

                            if response.get("interview_done"):
                                interview_done = True
                                break

            except Exception as e:
                print(f"❌ Error in generating response: {e}")
                break

        print("\n📝 Interview concluded. Here's your scorecard:")
        print("--------------------------------------------------")
        for idx, (answer, score, feedback) in enumerate(feedback_list, 1):
            print(f"Q{idx}: Answered -> {answer}")
            print(f"    ✅ Score: {score} | 🗒️ Feedback: {feedback}\n")
        print(f"🎯 Final Score: {total_score} / {max_questions * 10}")
        print("--------------------------------------------------\n")

if __name__ == "__main__":
    main()
