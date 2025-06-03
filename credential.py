# credential.py
import streamlit_authenticator as stauth # Pastikan import ini benar

# Daftar password yang ingin di-hash
passwords_to_hash = ['gantidenganpasswordsebenarnya1', 'gantidenganpasswordsebenarnya2']

# Buat instance Hasher dengan list password
hasher_instance = stauth.Hasher(passwords_to_hash)

# Generate hash-nya
hashed_passwords = hasher_instance.generate()

# Cetak hasilnya untuk disalin ke credentials.yaml
print(hashed_passwords)