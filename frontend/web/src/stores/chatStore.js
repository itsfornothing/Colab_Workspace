import { create } from 'zustand';

export const useChatStore = create((set) => ({
  messages: {},      // { [channelId]: Message[] }
  typingUsers: {},   // { [channelId]: string[] }
  activeUsers: {},   // { [channelId]: User[] }

  setMessages: (channelId, msgs) =>
    set((s) => ({ messages: { ...s.messages, [channelId]: msgs } })),

  addMessage: (channelId, msg) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [channelId]: [...(s.messages[channelId] || []), msg],
      },
    })),

  editMessage: (channelId, { message_id, content }) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [channelId]: (s.messages[channelId] || []).map((m) =>
          m.id === message_id ? { ...m, content, is_edited: true } : m
        ),
      },
    })),

  softDeleteMessage: (channelId, { message_id }) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [channelId]: (s.messages[channelId] || []).map((m) =>
          m.id === message_id ? { ...m, is_deleted: true } : m
        ),
      },
    })),

  updateReaction: (channelId, data) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [channelId]: (s.messages[channelId] || []).map((m) =>
          m.id === data.message_id ? { ...m, reactions: data.reactions } : m
        ),
      },
    })),

  setTypingUsers: (channelId, users) =>
    set((s) => ({ typingUsers: { ...s.typingUsers, [channelId]: users } })),

  addActiveUser: (channelId, user) =>
    set((s) => ({
      activeUsers: {
        ...s.activeUsers,
        [channelId]: [...(s.activeUsers[channelId] || []).filter((u) => u.id !== user.id), user],
      },
    })),

  removeActiveUser: (channelId, { user_id }) =>
    set((s) => ({
      activeUsers: {
        ...s.activeUsers,
        [channelId]: (s.activeUsers[channelId] || []).filter((u) => u.id !== user_id),
      },
    })),
}));
