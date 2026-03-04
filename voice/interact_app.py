import logging

from AppOpener import open, close


def open_app(recognized_text: str)-> None:
    logging.info(f"Opening: {recognized_text}")
   
    inp = recognized_text.lower()

    open(inp, match_closest=True, throw_error=True)


def close_app(recognized_text: str)-> None:
    logging.info(f"Closing: {recognized_text}")
   
    inp = recognized_text.lower()

    close(inp, match_closest=True)



if __name__ == "__main__":
    open_app()