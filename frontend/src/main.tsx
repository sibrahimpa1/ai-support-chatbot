import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ChatWidget from "./components/ChatWidget";
import "./index.css";
import Storefront from "./pages/Storefront";

// The dashboard (and its chart library) loads on demand, keeping the widget bundle small.
const DashboardLayout = lazy(() => import("./pages/dashboard/DashboardLayout"));
const Conversations = lazy(() => import("./pages/dashboard/Conversations"));
const Inbox = lazy(() => import("./pages/dashboard/Inbox"));
const KnowledgeBase = lazy(() => import("./pages/dashboard/KnowledgeBase"));
const Overview = lazy(() => import("./pages/dashboard/Overview"));
const ModelQuality = lazy(() => import("./pages/dashboard/ModelQuality"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Suspense fallback={null}>
      <Routes>
        <Route path="/" element={<Storefront />} />
        {/* Loaded inside an iframe by public/embed.js on any website. */}
        <Route path="/widget" element={<ChatWidget mode="embedded" />} />
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<Overview />} />
          <Route path="inbox" element={<Inbox />} />
          <Route path="inbox/:ticketId" element={<Inbox />} />
          <Route path="conversations" element={<Conversations />} />
          <Route path="conversations/:conversationId" element={<Conversations />} />
          <Route path="knowledge-base" element={<KnowledgeBase />} />
          <Route path="model-quality" element={<ModelQuality />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  </StrictMode>,
);
