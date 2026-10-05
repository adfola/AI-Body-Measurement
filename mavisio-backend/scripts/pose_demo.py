import time

import cv2

from app.core.pose_detector import PoseDetector


def main() -> None:
    detector = PoseDetector(model_complexity=1)
    camera = cv2.VideoCapture(0)
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            width = 480
            frame = cv2.resize(frame, (width, int(width * frame.shape[0] / frame.shape[1])))
            started = time.perf_counter()
            result = detector.process_frame(frame)
            milliseconds = (time.perf_counter() - started) * 1000
            if result and result["px"]:
                for x, y, visibility in result["px"].values():
                    if visibility > 0.5:
                        cv2.circle(frame, (int(x), int(y)), 4, (0, 210, 120), -1)
            cv2.putText(frame, f"{milliseconds:.0f} ms", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 230, 220), 2)
            cv2.imshow("Mavisio pose demo (q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        detector.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
