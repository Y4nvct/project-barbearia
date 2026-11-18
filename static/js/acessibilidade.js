document.addEventListener("DOMContentLoaded", () => {
  const botaoEscuro = document.getElementById(
    "alternar-modo-escuro"
  );

  const botaoContraste = document.getElementById(
    "alternar-contraste"
  );

  const iconeTema = document.getElementById("icone-tema");

  const chaveTema = "tema-barbearia";
  let tema = "claro";

  try {
    const temaSalvo = localStorage.getItem(chaveTema);

    if (["claro", "escuro", "alto-contraste"].includes(temaSalvo)) {
      tema = temaSalvo;
    }
  } catch (erro) {
    // Utiliza o modo claro se o armazenamento falhar.
  }

  function aplicarTema(novoTema) {
    tema = novoTema;

    const escuro = tema === "escuro";
    const contraste = tema === "alto-contraste";

    document.body.classList.toggle("modo-escuro", escuro);
    document.body.classList.toggle(
      "alto-contraste",
      contraste
    );

    if (iconeTema) {
      iconeTema.textContent = escuro ? "☀" : "☾";
    }

    if (botaoEscuro) {
      const descricao = escuro
        ? "Ativar modo claro"
        : "Ativar modo escuro";

      botaoEscuro.setAttribute("aria-label", descricao);
      botaoEscuro.setAttribute("title", descricao);
      botaoEscuro.setAttribute(
        "aria-pressed", String(escuro)
      );
    }

    if (botaoContraste) {
      botaoContraste.textContent = contraste
        ? "Desativar alto contraste"
        : "Alto contraste";

      botaoContraste.setAttribute(
        "aria-pressed",
        String(contraste)
      );
    }

    try {
      localStorage.setItem(chaveTema, tema);
    } catch (erro) {
      // Os temas continuam funcionando nesta página.
    }
  }

  botaoEscuro?.addEventListener("click", () => {
    aplicarTema(tema === "escuro" ? "claro" : "escuro");
  });

  botaoContraste?.addEventListener("click", () => {
    aplicarTema(
      tema === "alto-contraste" ? "claro" : "alto-contraste"
    );
  });

  aplicarTema(tema);
});
