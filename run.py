import os
import sys
import webbrowser

# Add workspace directory to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from backend.server import run_server

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
            
    print("=" * 60)
    print("🎓 대학생 스마트 구독 & 고정 지출 리밸런싱 AI")
    print("   [PRD Step 1] 구독 데이터 입력 및 Vision OCR 엔진")
    print("=" * 60)
    print(f"👉 웹 브라우저에서 아래 주소로 접속하세요:")
    print(f"   http://localhost:{port}")
    print("=" * 60)
    
    # Run the server
    run_server(port)
