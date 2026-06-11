import { io, Socket } from "socket.io-client"

let socket: Socket | null = null

export function getSocket(): Socket {
  if (!socket) {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ""
    const wsUrl = baseUrl.replace(/^http/, "ws") || "http://localhost:8000"
    socket = io(`${wsUrl}/ws`, {
      transports: ["websocket", "polling"],
      autoConnect: false,
    })
  }
  return socket
}

export function connectSocket() {
  const s = getSocket()
  if (!s.connected) {
    s.connect()
  }
  return s
}

export function disconnectSocket() {
  if (socket?.connected) {
    socket.disconnect()
  }
}
