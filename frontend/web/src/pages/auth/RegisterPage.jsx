import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff } from 'lucide-react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { useAuth } from '@/hooks/useAuth';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

function getStrength(pw) {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return score;
}

const STRENGTH_LABELS = ['', 'Weak', 'Fair', 'Good', 'Strong'];
const STRENGTH_COLORS = ['', 'bg-danger', 'bg-warning', 'bg-yellow-400', 'bg-success'];

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm: '' });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const strength = getStrength(form.password);
  const pwMismatch = form.confirm && form.confirm !== form.password;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (pwMismatch) return;
    setError('');
    setLoading(true);
    try {
      await register({ full_name: form.full_name, email: form.email, password: form.password });
      toast.success('Account created! Please verify your email.');
      navigate('/login');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.response?.data?.email?.[0] || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-bg-base">
      <motion.div
        className="w-full max-w-[420px]"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center mx-auto mb-3">
            <span className="text-white text-xl font-bold">C</span>
          </div>
          <h1 className="text-2xl font-bold text-[var(--color-text-heading)]">Create your account</h1>
        </div>

        <div className="bg-bg-elevated rounded-xl shadow-card p-8">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/20 text-danger text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Full name"
              type="text"
              placeholder="Alice Vance"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required
            />
            <Input
              label="Email"
              type="email"
              placeholder="you@company.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />

            {/* Password + strength */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-[var(--color-text-body)]">Password</label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  placeholder="Min. 8 characters"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                  className="w-full h-11 px-3.5 pr-10 rounded-md text-[15px] bg-bg-elevated border border-[var(--color-border)] focus:border-[var(--color-border-focus)] focus:ring-2 focus:ring-primary/15 outline-none text-[var(--color-text-heading)] placeholder:text-[var(--color-text-hint)]"
                />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-hint)]">
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {form.password && (
                <div className="space-y-1">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map((i) => (
                      <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= strength ? STRENGTH_COLORS[strength] : 'bg-[var(--color-border)]'}`} />
                    ))}
                  </div>
                  <p className="text-xs text-[var(--color-text-hint)]">{STRENGTH_LABELS[strength]}</p>
                </div>
              )}
            </div>

            {/* Confirm password */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-[var(--color-text-body)]">Confirm password</label>
              <input
                type="password"
                placeholder="Repeat password"
                value={form.confirm}
                onChange={(e) => setForm({ ...form, confirm: e.target.value })}
                required
                className={`w-full h-11 px-3.5 rounded-md text-[15px] bg-bg-elevated border outline-none text-[var(--color-text-heading)] placeholder:text-[var(--color-text-hint)] transition-colors ${
                  pwMismatch
                    ? 'border-danger focus:ring-2 focus:ring-danger/20'
                    : form.confirm && !pwMismatch
                    ? 'border-success'
                    : 'border-[var(--color-border)] focus:border-[var(--color-border-focus)] focus:ring-2 focus:ring-primary/15'
                }`}
              />
              {pwMismatch && <p className="text-xs text-danger">Passwords do not match</p>}
            </div>

            <Button type="submit" loading={loading} disabled={pwMismatch} className="w-full h-11 mt-2">
              Create Account
            </Button>
          </form>

          <p className="text-center text-sm text-[var(--color-text-hint)] mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
