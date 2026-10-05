import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedLayout from "./components/ProtectedLayout";
import CustomersPage from "./pages/CustomersPage";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import MeasurePage from "./pages/MeasurePage";
import StudioPage from "./pages/StudioPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<CustomersPage />} />
            <Route path="/studio" element={<StudioPage />} />
            <Route path="/measure/:id" element={<MeasurePage />} />
            <Route path="/history/:id" element={<HistoryPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
