import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getStatus(): Observable<any> {
    return this.http.get(`${this.apiUrl}/api/status`);
  }

  getAlarmStatus(): Observable<any> {
    return this.http.get(`${this.apiUrl}/api/alarm/status`);
  }

  armAlarm(): Observable<any> {
    return this.http.post(`${this.apiUrl}/api/alarm/arm`, {});
  }

  deactivateAlarm(pin: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/api/alarm/deactivate`, { pin });
  }

  getPeopleCount(): Observable<any> {
    return this.http.get(`${this.apiUrl}/api/people-count`);
  }

  controlLed(action: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/api/led`, { action });
  }

  controlBuzzer(action: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/api/buzzer`, { action });
  }

  getAlarmEvents(): Observable<any> {
    return this.http.get(`${this.apiUrl}/api/alarm-events`);
  }
}
