import argparse


from .recorder import AudioRecorder


def main():
    """Main function to run when script is executed directly"""
    parser = argparse.ArgumentParser(
        description="Interactive audio recorder and transcriber with Whisper"
    )

    args = parser.parse_args()

    try:
        recorder = AudioRecorder()
        recorder.run_interactive()

    except KeyboardInterrupt:
        print("\nAu revoir !")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()