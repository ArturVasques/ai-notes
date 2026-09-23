import { Component, inject } from '@angular/core';
import { AuthService } from './core/auth/auth.service';
import { NotesService } from './features/notes/notes.service';

@Component({
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  private readonly auth = inject(AuthService);
  private readonly notes = inject(NotesService);

  readonly isAuthenticated = this.auth.isAuthenticated;

  login(): void {
    this.auth.login();
  }

  logout(): void {
    this.auth.logout();
  }

  async loadNotes(): Promise<void> {
    try {
      const notes = await this.notes.getNotes();
      console.log(notes);
    } catch (error) {
      console.error(error);
    }
  }
}
