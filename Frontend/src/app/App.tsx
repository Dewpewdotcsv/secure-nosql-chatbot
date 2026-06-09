import { ChatInterface } from "./components/ChatInterface";

export type UserRole = "admin" | "worker" | "user";

export default function App() {
  return (
    <ChatInterface
      role="admin"
      username="admin@example.com"
      onLogout={() => {}}
    />
  );
}
