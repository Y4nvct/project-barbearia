document.addEventListener("DOMContentLoaded", () => {
    const notificacoes = document.querySelectorAll(".aviso");

    notificacoes.forEach((notificacao) => {
        setTimeout(() => {
            notificacao.remove();
        }, 5000);
    });
});
