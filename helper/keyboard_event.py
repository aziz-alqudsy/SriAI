import keyboard

print("▶️ Tekan tombol apa saja (Ctrl+C untuk keluar)")

try:
    while True:
        event = keyboard.read_event()
        if event.event_type == keyboard.KEY_DOWN:
            print("🔘 Tombol ditekan:", event.name)
except KeyboardInterrupt:
    print("\n❌ Program dihentikan oleh user.")
