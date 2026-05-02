import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '@/hooks/useAuth';
import LoginPage from '@/pages/auth/LoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import WorkspacePickerPage from '@/pages/WorkspacePickerPage';
import WorkspaceShell from '@/pages/workspace/WorkspaceShell';
import HomePage from '@/pages/workspace/HomePage';
import ChatPage from '@/pages/workspace/ChatPage';
import DocumentsPage from '@/pages/workspace/DocumentsPage';
import DocumentEditorPage from '@/pages/workspace/DocumentEditorPage';
import CallsPage from '@/pages/workspace/CallsPage';
import CallRoomPage from '@/pages/workspace/CallRoomPage';
import MembersPage from '@/pages/workspace/MembersPage';
import SettingsPage from '@/pages/workspace/SettingsPage';
import NotificationsPage from '@/pages/workspace/NotificationsPage';
import ProfilePage from '@/pages/ProfilePage';

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Authenticated */}
      <Route path="/" element={<ProtectedRoute><Navigate to="/workspaces" replace /></ProtectedRoute>} />
      <Route path="/workspaces" element={<ProtectedRoute><WorkspacePickerPage /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />

      {/* Workspace shell */}
      <Route path="/w/:workspaceId" element={<ProtectedRoute><WorkspaceShell /></ProtectedRoute>}>
        <Route index element={<Navigate to="home" replace />} />
        <Route path="home" element={<HomePage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="chat/:channelId" element={<ChatPage />} />
        <Route path="docs" element={<DocumentsPage />} />
        <Route path="docs/:docId" element={<DocumentEditorPage />} />
        <Route path="calls" element={<CallsPage />} />
        <Route path="calls/:roomId" element={<CallRoomPage />} />
        <Route path="members" element={<MembersPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
