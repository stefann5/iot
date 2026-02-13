import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ApiService } from '../../services/api.service';
import { WebSocketService } from '../../services/websocket.service';
import { MessageService } from 'primeng/api';
import { environment } from '../../../environments/environment';
import { SafeUrlPipe } from '../../pipes/safe-url.pipe';

import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { TagModule } from 'primeng/tag';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { PanelModule } from 'primeng/panel';
import { KnobModule } from 'primeng/knob';
import { ToolbarModule } from 'primeng/toolbar';
import { DividerModule } from 'primeng/divider';
import { BadgeModule } from 'primeng/badge';
import { PasswordModule } from 'primeng/password';

interface SensorState {
  value: any;
  name: string;
  type: string;
  timestamp: number | null;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    CardModule, ButtonModule, TagModule, DialogModule,
    InputTextModule, PanelModule, KnobModule, ToolbarModule,
    DividerModule, BadgeModule, PasswordModule, SafeUrlPipe,
  ],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit, OnDestroy {
  sensors: Record<string, SensorState> = {};
  alarmState = 'DISARMED';
  alarmReason = '';
  peopleCount = 0;
  lastDirection = '';
  pinInput = '';
  showPinDialog = false;
  grafanaUrl = '';
  wsConnected = false;

  private wsSub: Subscription | null = null;
  private pollInterval: any;

  constructor(
    private api: ApiService,
    private ws: WebSocketService,
    private messageService: MessageService,
  ) {}

  ngOnInit(): void {
    this.grafanaUrl = `${environment.grafanaUrl}/d/pi1-sensors/pi1-door-control-system-sensors?orgId=1&kiosk&refresh=5s`;

    this.ws.connect();
    this.wsSub = this.ws.messages$.subscribe((msg) => this.handleWsMessage(msg));

    this.loadStatus();
    this.pollInterval = setInterval(() => this.loadStatus(), 10000);
  }

  ngOnDestroy(): void {
    this.wsSub?.unsubscribe();
    clearInterval(this.pollInterval);
  }

  loadStatus(): void {
    this.api.getStatus().subscribe({
      next: (data) => {
        this.sensors = data.sensors || {};
        this.alarmState = data.alarm?.state || 'DISARMED';
        this.alarmReason = data.alarm?.reason || '';
        this.peopleCount = data.people?.count || 0;
        this.lastDirection = data.people?.last_direction || '';
        this.wsConnected = true;
      },
      error: () => { this.wsConnected = false; },
    });
  }

  handleWsMessage(msg: any): void {
    if (msg.type === 'initial_state') {
      this.sensors = msg.sensors || this.sensors;
      this.alarmState = msg.alarm?.state || this.alarmState;
      this.alarmReason = msg.alarm?.reason || '';
      this.peopleCount = msg.people?.count || 0;
      return;
    }

    if (msg.alarm) {
      const prev = this.alarmState;
      this.alarmState = msg.alarm.state || this.alarmState;
      this.alarmReason = msg.alarm.reason || this.alarmReason;

      if (msg.alarm.state === 'ALARM' && prev !== 'ALARM') {
        this.messageService.add({
          severity: 'error',
          summary: 'ALARM TRIGGERED',
          detail: msg.alarm.reason || 'Motion or door breach detected! Enter PIN to deactivate.',
          life: 10000,
        });
      }
      if (msg.alarm.state === 'ARMING' && prev !== 'ARMING') {
        this.messageService.add({
          severity: 'info',
          summary: 'System Arming',
          detail: 'System will arm in 10 seconds. Enter PIN to cancel.',
          life: 5000,
        });
      }
      if (msg.alarm.state === 'ARMED' && prev !== 'ARMED') {
        this.messageService.add({
          severity: 'warn',
          summary: 'System Armed',
          detail: 'Alarm system has been armed.',
          life: 5000,
        });
      }
      if (msg.alarm.state === 'DISARMED' && (prev === 'ALARM' || prev === 'ARMED' || prev === 'ARMING')) {
        this.alarmReason = '';
        this.messageService.add({
          severity: 'success',
          summary: 'Alarm Deactivated',
          detail: 'The alarm has been successfully deactivated.',
          life: 5000,
        });
      }
    }

    if (msg.people) {
      this.peopleCount = msg.people.count ?? this.peopleCount;
      this.lastDirection = msg.people.last_direction || this.lastDirection;
    }

    if (msg.readings) {
      for (const r of msg.readings) {
        if (r.sensor_id && this.sensors[r.sensor_id]) {
          this.sensors[r.sensor_id].value = r.value;
          this.sensors[r.sensor_id].timestamp = r.timestamp;
        }
      }
    }
  }

  armAlarm(): void {
    this.api.armAlarm().subscribe({
      next: () => {
        this.messageService.add({
          severity: 'info', summary: 'Arming', detail: 'Arm command sent', life: 3000,
        });
      },
    });
  }

  showDeactivateDialog(): void {
    this.pinInput = '';
    this.showPinDialog = true;
  }

  deactivateAlarm(): void {
    this.api.deactivateAlarm(this.pinInput).subscribe({
      next: () => {
        this.showPinDialog = false;
        this.pinInput = '';
        this.messageService.add({
          severity: 'info', summary: 'Deactivating', detail: 'Deactivate command sent', life: 3000,
        });
      },
    });
  }

  controlLed(action: string): void {
    this.api.controlLed(action).subscribe();
  }

  controlBuzzer(action: string): void {
    this.api.controlBuzzer(action).subscribe();
  }

  getAlarmSeverity(): "success" | "info" | "warning" | "danger" {
    switch (this.alarmState) {
      case 'ALARM': return 'danger';
      case 'ARMED': return 'warning';
      case 'ARMING': return 'info';
      default: return 'success';
    }
  }

  getSensorIcon(type: string): string {
    switch (type) {
      case 'button': return 'pi pi-sign-in';
      case 'led': return 'pi pi-sun';
      case 'ultrasonic': return 'pi pi-arrows-h';
      case 'buzzer': return 'pi pi-volume-up';
      case 'pir': return 'pi pi-eye';
      case 'membrane_switch': return 'pi pi-th-large';
      default: return 'pi pi-cog';
    }
  }

  getSensorDisplayValue(sensor: SensorState): string {
    switch (sensor.type) {
      case 'button': return sensor.value === 1 ? 'CLOSED' : 'OPEN';
      case 'led': return sensor.value === 1 ? 'ON' : 'OFF';
      case 'buzzer': return sensor.value === 1 ? 'BEEPING' : 'OFF';
      case 'pir': return sensor.value === 1 ? 'MOTION' : 'No Motion';
      case 'ultrasonic': return `${sensor.value} cm`;
      case 'membrane_switch': return sensor.value ? `Key: ${sensor.value}` : 'Idle';
      default: return String(sensor.value);
    }
  }

  getSensorSeverity(sensor: SensorState): "success" | "info" | "warning" | "danger" {
    switch (sensor.type) {
      case 'pir': return sensor.value === 1 ? 'danger' : 'success';
      case 'button': return sensor.value === 1 ? 'warning' : 'success';
      case 'led': return sensor.value === 1 ? 'warning' : 'info';
      case 'buzzer': return sensor.value === 1 ? 'danger' : 'info';
      default: return 'info';
    }
  }

  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }
}
