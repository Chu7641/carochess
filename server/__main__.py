"""Chạy: python -m server [--port 8000] [--host 0.0.0.0] [--reload]"""

import argparse

import uvicorn

from .app import DIST, lan_addresses


def main():
    parser = argparse.ArgumentParser(description="Máy chủ cờ caro chơi qua mạng LAN.")
    parser.add_argument("--host", default="0.0.0.0", help="mặc định nghe trên mọi card mạng")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="tự khởi động lại khi sửa code")
    args = parser.parse_args()
    print(f"Cờ caro LAN đang chạy. Mở trên máy này: http://localhost:{args.port}")
    for ip in lan_addresses():
        print(f"  Máy khác cùng mạng LAN: http://{ip}:{args.port}")
    if not DIST.is_dir():
        print("  (Chưa build giao diện: chạy `npm run build` trong thư mục web.)")
    uvicorn.run("server.app:app", host=args.host, port=args.port, reload=args.reload,
                log_level="info")


if __name__ == "__main__":
    main()
