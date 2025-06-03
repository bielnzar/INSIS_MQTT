<template>
  <div class="flex items-center justify-center min-h-screen bg-slate-200">
    <div class="bg-white p-8 md:p-12 rounded-xl shadow-2xl w-full max-w-md">
      <h2 class="text-3xl font-bold text-slate-700 mb-8 text-center">
        Login Dashboard Cuaca
      </h2>
      <form @submit.prevent="handleLogin">
        <div class="mb-6">
          <label
            for="username"
            class="block text-sm font-medium text-slate-600 mb-1"
            >Username</label
          >
          <input
            type="text"
            id="username"
            v-model="username"
            required
            class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-600 transition-colors"
            placeholder="Masukkan username"
          />
        </div>
        <div class="mb-6">
          <label
            for="password"
            class="block text-sm font-medium text-slate-600 mb-1"
            >Password</label
          >
          <input
            type="password"
            id="password"
            v-model="password"
            required
            class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-600 transition-colors"
            placeholder="Masukkan password"
          />
        </div>
        <div v-if="error" class="mb-6 text-red-600 text-sm bg-red-100 p-3 rounded-md">
          {{ error }}
        </div>
        <button
          type="submit"
          class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors duration-300 ease-in-out transform hover:scale-105"
        >
          Masuk
        </button>
      </form>
       <p class="text-xs text-center text-gray-500 mt-6">
        Hint: coba user: <code class="bg-gray-200 px-1 rounded">admin</code>, pass: <code class="bg-gray-200 px-1 rounded">password123</code>
      </p>
    </div>
  </div>
</template>

<script>
export default {
  name: "LoginPage",
  data() {
    return {
      username: "",
      password: "",
      error: "",
    };
  },
  methods: {
    handleLogin() {
      // Ganti dengan logika autentikasi yang sebenarnya jika perlu
      if (this.username === "admin" && this.password === "password123") {
        this.error = "";
        this.$emit("loggedIn");
      } else {
        this.error = "Username atau password salah.";
      }
    },
  },
};
</script>