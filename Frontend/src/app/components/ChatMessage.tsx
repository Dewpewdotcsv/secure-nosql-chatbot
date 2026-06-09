import React from "react";
import { Bot, User } from "lucide-react";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
};

type ChatMessageProps = {
  message: Message;
};

type ContentBlock =
  | { type: "text"; text: string }
  | { type: "table"; headers: string[]; rows: string[][] };

function parseMessageContent(content: string): ContentBlock[] {
  const lines = content.split("\n");
  const blocks: ContentBlock[] = [];
  let currentTextLines: string[] = [];
  let currentTableLines: string[] = [];

  const flushText = () => {
    if (currentTextLines.length > 0) {
      blocks.push({ type: "text", text: currentTextLines.join("\n") });
      currentTextLines = [];
    }
  };

  const flushTable = () => {
    if (currentTableLines.length > 0) {
      const rowLines = currentTableLines.filter((line) => line.trim().startsWith("|"));
      if (rowLines.length > 0) {
        // Parse headers from the first row
        const headers = rowLines[0]
          .split("|")
          .slice(1, -1)
          .map((cell) => cell.trim());

        // Parse data rows
        const rows = rowLines.slice(1).map((line) =>
          line
            .split("|")
            .slice(1, -1)
            .map((cell) => cell.trim())
        );

        blocks.push({ type: "table", headers, rows });
      }
      currentTableLines = [];
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    // Classify line as part of a table if it matches typical ASCII line delimiters
    const isTableLine =
      trimmed.startsWith("|") ||
      trimmed.startsWith("+--") ||
      (trimmed.startsWith("+") && trimmed.endsWith("+") && trimmed.includes("-"));

    if (isTableLine) {
      flushText();
      currentTableLines.push(line);
    } else {
      flushTable();
      currentTextLines.push(line);
    }
  }
  flushText();
  flushTable();

  return blocks;
}

function renderTextWithBold(text: string) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index} className="font-semibold">{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const blocks = parseMessageContent(message.content);

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"} items-start`}>
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center shadow-sm ${
          isUser ? "bg-blue-600" : "bg-gray-800"
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-white" />
        )}
      </div>
      <div
        className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? "bg-blue-600 text-white rounded-tr-sm shadow-md"
            : "bg-white text-gray-900 rounded-tl-sm border border-gray-200 shadow-sm"
        }`}
      >
        <div className="space-y-3">
          {blocks.map((block, idx) => {
            if (block.type === "text") {
              return (
                <p key={idx} className="whitespace-pre-wrap leading-relaxed">
                  {renderTextWithBold(block.text)}
                </p>
              );
            } else {
              return (
                <div key={idx} className="overflow-x-auto my-3 border border-gray-200 rounded-xl shadow-inner bg-gray-50/50 max-w-full">
                  <table className="min-w-full divide-y divide-gray-200 text-xs">
                    <thead className="bg-gray-50 font-bold text-gray-700">
                      <tr>
                        {block.headers.map((h, i) => (
                          <th
                            key={i}
                            className="px-3 py-2.5 text-left tracking-wider whitespace-nowrap uppercase text-[10px] text-gray-500 font-semibold border-b border-gray-200"
                          >
                            {h.replace(/->/g, "»")}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 text-gray-600 bg-white">
                      {block.rows.map((row, rowIndex) => (
                        <tr key={rowIndex} className="hover:bg-gray-50/80 transition-colors">
                          {row.map((cell, cellIndex) => {
                            const isMasked = cell.includes("MASKED");
                            return (
                              <td key={cellIndex} className="px-3 py-2 whitespace-nowrap font-medium text-gray-700">
                                {isMasked ? (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[9px] font-semibold bg-amber-50 text-amber-800 border border-amber-200 animate-pulse">
                                    🔒 Masked
                                  </span>
                                ) : (
                                  cell
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            }
          })}
        </div>
        <p
          className={`text-[10px] mt-2 text-right select-none ${
            isUser ? "text-blue-200" : "text-gray-400"
          }`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}
