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
import { InputNumberModule } from 'primeng/inputnumber';
import { ProgressBarModule } from 'primeng/progressbar';

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
    InputNumberModule, ProgressBarModule,
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

  // Timer state (Feature 8)
  timerDisplay = '00:00';
  timerRemaining = 0;
  timerRunning = false;
  timerBlinking = false;
  timerInputMinutes = 5;
  timerBtnSeconds = 10;

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
        // Timer state
        if (data.timer) {
          this.timerDisplay = data.timer.display || '00:00';
          this.timerRemaining = data.timer.remaining || 0;
          this.timerRunning = data.timer.running || false;
          this.timerBlinking = data.timer.blinking || false;
          this.timerBtnSeconds = data.timer.btn_seconds || 10;
        }
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
      // Timer initial state
      if (msg.timer) {
        this.timerDisplay = msg.timer.display || '00:00';
        this.timerRemaining = msg.timer.remaining || 0;
        this.timerRunning = msg.timer.running || false;
        this.timerBlinking = msg.timer.blinking || false;
        this.timerBtnSeconds = msg.timer.btn_seconds || 10;
      }
      return;
    }

    // Handle timer updates
    if (msg.timer) {
      this.timerDisplay = msg.timer.display || this.timerDisplay;
      this.timerRemaining = msg.timer.remaining ?? this.timerRemaining;
      this.timerRunning = msg.timer.running ?? this.timerRunning;
      this.timerBlinking = msg.timer.blinking ?? this.timerBlinking;
      if (msg.timer.blinking && !this.timerBlinking) {
        this.messageService.add({
          severity: 'warn',
          summary: "Time's Up!",
          detail: 'Kitchen timer finished. Press BTN to acknowledge.',
          life: 5000,
        });
      }
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
          // Parse JSON values for complex sensor types
          let value = r.value;
          if (typeof value === 'string' && (value.startsWith('{') || value.startsWith('['))) {
            try {
              value = JSON.parse(value);
            } catch (e) {
              // Keep as string if parsing fails
            }
          }
          this.sensors[r.sensor_id].value = value;
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

  // Timer controls (Feature 8)
  timerSetTime(): void {
    const seconds = this.timerInputMinutes * 60;
    this.api.timerSetTime(seconds).subscribe();
  }

  timerStart(): void {
    this.api.timerStart().subscribe();
  }

  timerStop(): void {
    this.api.timerStop().subscribe();
  }

  timerAddSeconds(): void {
    this.api.timerAddSeconds(this.timerBtnSeconds).subscribe();
  }

  timerPressBTN(): void {
    // Simulates pressing the physical BTN - stops blinking when timer is done
    this.api.timerAddSeconds(0).subscribe();
  }

  timerUpdateBtnSeconds(): void {
    this.api.timerSetBtnSeconds(this.timerBtnSeconds).subscribe();
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
      case 'gyroscope': return 'pi pi-compass';
      case 'dht': return 'pi pi-cloud';
      case 'lcd': return 'pi pi-desktop';
      case 'segment_display': return 'pi pi-clock';
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
      case 'gyroscope':
        const gsg = typeof sensor.value === 'object' ? sensor.value : {};
        return gsg.significant ? 'MOVEMENT!' : 'Stable';
      case 'dht':
        const dht = typeof sensor.value === 'object' ? sensor.value : {};
        return `${dht.temperature || 0}°C / ${dht.humidity || 0}%`;
      case 'lcd':
        const lcd = typeof sensor.value === 'object' ? sensor.value : {};
        return lcd.line1 || 'Idle';
      case 'segment_display':
        const sd = typeof sensor.value === 'object' ? sensor.value : {};
        return sd.display || '00:00';
      default: return String(sensor.value);
    }
  }

  getSensorSeverity(sensor: SensorState): "success" | "info" | "warning" | "danger" {
    switch (sensor.type) {
      case 'pir': return sensor.value === 1 ? 'danger' : 'success';
      case 'button': return sensor.value === 1 ? 'warning' : 'success';
      case 'led': return sensor.value === 1 ? 'warning' : 'info';
      case 'buzzer': return sensor.value === 1 ? 'danger' : 'info';
      case 'gyroscope':
        const gsg = typeof sensor.value === 'object' ? sensor.value : {};
        return gsg.significant ? 'danger' : 'success';
      case 'dht': return 'info';
      case 'lcd': return 'info';
      case 'segment_display':
        const sd = typeof sensor.value === 'object' ? sensor.value : {};
        return sd.blinking ? 'warning' : 'info';
      default: return 'info';
    }
  }

  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }
}
