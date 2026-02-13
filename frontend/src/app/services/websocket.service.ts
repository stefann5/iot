import { Injectable, OnDestroy } from '@angular/core';
import { Subject, Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private socket: WebSocket | null = null;
  private messagesSubject = new Subject<any>();
  private reconnectInterval = 3000;
  private reconnectTimer: any;

  messages$: Observable<any> = this.messagesSubject.asObservable();

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return;
    }

    this.socket = new WebSocket(environment.wsUrl);

    this.socket.onopen = () => {
      console.log('[WS] Connected');
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.messagesSubject.next(data);
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };

    this.socket.onclose = () => {
      console.log('[WS] Disconnected, reconnecting...');
      this.scheduleReconnect();
    };

    this.socket.onerror = (error) => {
      console.error('[WS] Error:', error);
      this.socket?.close();
    };
  }

  private scheduleReconnect(): void {
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectInterval);
  }

  send(data: any): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    }
  }

  ngOnDestroy(): void {
    clearTimeout(this.reconnectTimer);
    this.socket?.close();
  }
}
