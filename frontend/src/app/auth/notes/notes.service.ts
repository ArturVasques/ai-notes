import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../auth.service';

@Injectable({ providedIn: 'root' })
export class NotesService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  async getNotes(): Promise<unknown> {
    const token = await this.auth.getAccessToken();

    return firstValueFrom(
      this.http.get('http://localhost:8000/notes', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }),
    );
  }
}