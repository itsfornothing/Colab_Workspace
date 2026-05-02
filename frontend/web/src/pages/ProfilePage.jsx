import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { ArrowLeft, Camera, Save, Moon, Sun, Monitor } from 'lucide-react';
import api from '@/lib/axiosClient';
import { useAuth } from '@/hooks/useAuth';
import { useUiStore } from '@/stores/uiStore';
import Avatar from '@/components/ui/Avatar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import toast from 'react-hot-toast';
import { clsx } from 'clsx';

const THEMES = [
  { value: 'light',  label: 'Light',  icon: Sun },
  { value: 'dark',   label: 'Dark',   icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, setUser, logout } = useAuth();
  const { theme, setTheme } = useUiStore();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const profileMutation = useMutation({
    mutationFn: () => api.patch('/api/auth/profile/', { full_name: fullName }),
    onSuccess: ({ data }) => { setUser(data); toast.success('Profile updated'); },
    onError: () => toast.error('Failed to update profile'),
  });

  const passwordMutation = useMutation({
    mutationFn: () => api.post('/api/auth/change-password/', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
    onSuccess: () => {
      toast.success('Password changed');
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
    },
    onError: () => toast.error('Failed to change password'),
  });

  const avatarMutation = useMutation({
    mutationFn: async (file) => {
      const fd = new FormData();
      fd.append('avatar', file);
      const { data } = await api.patch('/api/auth/profile/', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      return data;
    },
    onSuccess: (data) => { setUser(data); toast.success('Avatar updated'); },
    onError: () => toast.error('Failed to upload avatar'),
  });

  return (
    <div className="max-w-2xl mx-auto p-6 lg:p-8">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-sm text-[var(--color-text-hint)] hover:text-[var(--color-text-body)] mb-6 transition-colors"
      >
        <ArrowLeft size={16} /> Back
      </button>

      <h1 className="text-h1 mb-8">Profile</h1>

      {/* Avatar */}
      <section className="bg-bg-elevated rounded-xl border border-[var(--color-border)] p-6 mb-6">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Avatar src={user?.avatar_url} name={user?.full_name} size="xl" />
            <label className="absolute bottom-0 right-0 w-7 h-7 bg-primary rounded-full flex items-center justify-center cursor-pointer hover:bg-primary-dark transition-colors">
              <Camera size={14} className="text-white" />
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && avatarMutation.mutate(e.target.files[0])}
              />
            </label>
          </div>
          <div>
            <p className="font-semibold text-[var(--color-text-heading)]">{user?.full_name}</p>
            <p className="text-sm text-[var(--color-text-hint)]">{user?.email}</p>
          </div>
        </div>
      </section>

      {/* Profile info */}
      <section className="bg-bg-elevated rounded-xl border border-[var(--color-border)] p-6 mb-6">
        <h2 className="text-h3 mb-4">Personal Info</h2>
        <div className="space-y-4">
          <Input label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <Input label="Email" value={user?.email || ''} disabled />
          <div className="flex justify-end">
            <Button onClick={() => profileMutation.mutate()} loading={profileMutation.isPending}>
              <Save size={16} className="mr-1.5" /> Save
            </Button>
          </div>
        </div>
      </section>

      {/* Password */}
      <section className="bg-bg-elevated rounded-xl border border-[var(--color-border)] p-6 mb-6">
        <h2 className="text-h3 mb-4">Change Password</h2>
        <div className="space-y-4">
          <Input label="Current password" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
          <Input label="New password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          <Input label="Confirm new password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
          <div className="flex justify-end">
            <Button
              onClick={() => passwordMutation.mutate()}
              disabled={!currentPassword || !newPassword || newPassword !== confirmPassword || passwordMutation.isPending}
              loading={passwordMutation.isPending}
            >
              Update Password
            </Button>
          </div>
        </div>
      </section>

      {/* Theme */}
      <section className="bg-bg-elevated rounded-xl border border-[var(--color-border)] p-6 mb-6">
        <h2 className="text-h3 mb-4">Appearance</h2>
        <div className="flex gap-3">
          {THEMES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              onClick={() => setTheme(value)}
              className={clsx(
                'flex-1 flex flex-col items-center gap-2 p-3 rounded-xl border transition-colors',
                theme === value
                  ? 'border-primary bg-primary-light text-primary'
                  : 'border-[var(--color-border)] hover:border-primary/50 text-[var(--color-text-hint)]'
              )}
            >
              <Icon size={20} />
              <span className="text-xs font-medium">{label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Sign out */}
      <Button variant="ghost" className="w-full text-danger hover:bg-danger/10" onClick={logout}>
        Sign out
      </Button>
    </div>
  );
}
