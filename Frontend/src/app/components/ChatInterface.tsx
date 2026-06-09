import { useState, useRef, useEffect } from "react";
import { Send, LogOut, Database, Users, BarChart3, Settings, ChevronRight } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import type { Message } from "./ChatMessage";
import type { UserRole } from "../App";

type ChatInterfaceProps = {
  role: UserRole;
  username: string;
  onLogout: () => void;
};

type QuickAction = {
  label: string;
  query: string;
  icon: React.ReactNode;
};

const ROLE_CONFIG: Record<
  UserRole,
  {
    label: string;
    color: string;
    bg: string;
    border: string;
    quickActions: QuickAction[];
    description: string;
  }
> = {
  admin: {
    label: "Admin",
    color: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-200",
    description: "Full access — all users, database records, and settings",
    quickActions: [
      { label: "Show all loans", query: "give all records", icon: <Database className="w-3.5 h-3.5" /> },
      { label: "Find approved loans", query: "show approved applications", icon: <ChevronRight className="w-3.5 h-3.5" /> },
      { label: "Maximum loan amount", query: "give the maximum loan taken by a candidate", icon: <BarChart3 className="w-3.5 h-3.5" /> },
      { label: "Multiple locations", query: "give me all the people from bangalore and mumbai", icon: <Users className="w-3.5 h-3.5" /> },
    ],
  },
  worker: {
    label: "Worker",
    color: "text-amber-600",
    bg: "bg-amber-50",
    border: "border-amber-200",
    description: "Restricted access — PII columns will be dynamically masked",
    quickActions: [
      { label: "Show all loans", query: "give all records", icon: <Database className="w-3.5 h-3.5" /> },
      { label: "Pending loans", query: "show pending applications", icon: <ChevronRight className="w-3.5 h-3.5" /> },
    ],
  },
  user: {
    label: "User",
    color: "text-green-600",
    bg: "bg-green-50",
    border: "border-green-200",
    description: "Personal access — isolated to your own loan profile records only",
    quickActions: [
      { label: "My loan status", query: "give all records", icon: <Database className="w-3.5 h-3.5" /> },
    ],
  },
};

export function ChatInterface({ role, username, onLogout }: ChatInterfaceProps) {
  const config = ROLE_CONFIG[role];
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: `Welcome back, **${username}**! You're signed in as **${config.label}**.\n\n${config.description}.\n\nHow can I help you query the database today?`,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);





  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  async function sendMessage(content: string) {
    if (!content.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: content.trim(),
          username: username,
          role: role,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const botMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, botMsg]);
      } else {
        const errData = await res.json().catch(() => ({}));
        const botMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: `❌ **Error querying database:** ${errData.detail || "Unknown error occurred."}`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, botMsg]);
      }
    } catch (err) {
      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `❌ **Connection error:** Could not reach the API server. Please verify the backend is running.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } finally {
      setIsTyping(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-xl ${config.bg} ${config.border} border flex items-center justify-center`}>
            <Database className={`w-4 h-4 ${config.color}`} />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900">DB Chatbot</h1>
            <p className="text-xs text-gray-500">{username}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${config.bg} ${config.color} ${config.border} border`}>
            {config.label}
          </span>
          {/* Logout button removed */}
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        {isTyping && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
              <Database className="w-4 h-4 text-white" />
            </div>
            <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-tl-sm">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick actions */}
      <div className="px-4 pb-2 flex gap-2 overflow-x-auto">
        {config.quickActions.map((action) => (
          <button
            key={action.label}
            onClick={() => sendMessage(action.query)}
            className="flex-shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors"
          >
            {action.icon}
            {action.label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-200 px-4 py-3">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask as ${config.label}...`}
            rows={1}
            className="flex-1 resize-none border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent max-h-32 overflow-y-auto"
            style={{ lineHeight: "1.5" }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isTyping}
            className="flex-shrink-0 w-10 h-10 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:cursor-not-allowed text-white rounded-xl flex items-center justify-center transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1.5 text-center">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>


    </div>
  );
}
