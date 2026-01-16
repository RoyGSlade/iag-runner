import { BrowserRouter, Route, Routes } from "react-router-dom";
import CharacterCreation from "./pages/CharacterCreation.jsx";
import SessionView from "./pages/SessionView.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CharacterCreation />} />
        <Route path="/session/:sessionId" element={<SessionView />} />
      </Routes>
    </BrowserRouter>
  );
}
