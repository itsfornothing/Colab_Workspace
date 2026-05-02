// Re-exports react-hot-toast helpers with project styling
export { toast } from 'react-hot-toast';

// Convenience wrappers
import { toast } from 'react-hot-toast';

export const showSuccess = (msg) => toast.success(msg);
export const showError   = (msg) => toast.error(msg);
export const showInfo    = (msg) => toast(msg, { icon: 'ℹ️' });
