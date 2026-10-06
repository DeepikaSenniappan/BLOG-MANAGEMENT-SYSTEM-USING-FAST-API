"""Tiny local SMTP capture server for development (no external delivery)."""

import argparse
import asyncio
from email import policy
from email.parser import BytesParser


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    writer.write(b"220 localhost Blog API development inbox\r\n")
    await writer.drain()
    message_lines: list[bytes] = []
    in_data = False

    try:
        while line := await reader.readline():
            command = line.decode("utf-8", errors="replace").strip()
            upper = command.upper()

            if in_data:
                if command == ".":
                    in_data = False
                    raw_message = b"\r\n".join(message_lines)
                    parsed = BytesParser(policy=policy.default).parsebytes(raw_message)
                    print("\n" + "=" * 68)
                    print(f"To: {parsed.get('To', '')}")
                    print(f"Subject: {parsed.get('Subject', '')}")
                    print("-" * 68)
                    print(parsed.get_body(preferencelist=("plain",)).get_content()
                          if parsed.get_body(preferencelist=("plain",)) else raw_message.decode("utf-8", errors="replace"))
                    print("=" * 68, flush=True)
                    message_lines.clear()
                    writer.write(b"250 Message captured locally\r\n")
                else:
                    message_lines.append(line.rstrip(b"\r\n"))
                await writer.drain()
                continue

            if upper.startswith(("EHLO", "HELO")):
                writer.write(b"250-localhost\r\n250 HELP\r\n")
            elif upper.startswith(("MAIL FROM:", "RCPT TO:")):
                writer.write(b"250 OK\r\n")
            elif upper == "DATA":
                in_data = True
                writer.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
            elif upper in {"QUIT", "QUIT "}:
                writer.write(b"221 Bye\r\n")
                await writer.drain()
                break
            elif upper in {"RSET", "NOOP"}:
                writer.write(b"250 OK\r\n")
            else:
                writer.write(b"250 OK\r\n")
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            # Clients may close early (e.g. health checks or cancelled SMTP
            # sends); that should not produce an unhandled asyncio callback.
            pass


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()
    server = await asyncio.start_server(handle_client, args.host, args.port)
    print(f"Local email inbox listening on {args.host}:{args.port}. Press Ctrl+C to stop.", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLocal email inbox stopped.")
