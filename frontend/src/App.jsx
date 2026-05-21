import { Routes, Route } from "react-router-dom";

function Home() {
  return <h1>Forum Wędkarskie 🎣</h1>;
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      {/* Kolejne strony dodasz tutaj */}
    </Routes>
  );
}

export default App;
