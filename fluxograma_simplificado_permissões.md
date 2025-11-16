Usuário loga →
          │
          ▼
Verifica perfil →
│       │    │    │    │    │
│      ▼    ▼    ▼    ▼    ▼
│  Admin Coord. Sup. Prof. Admn. Colab.
│      │    │    │    │    │
│      ▼    ▼    ▼    ▼    ▼
│      Telas/restrições conforme perfil
│      │    │    │    │    │
▼------┴----┴----┴----┴----┘
           |
           ▼
 Ações/Telas liberadas apenas se o usuário pertence ao perfil correto



Educadora loga →
     Vê só suas turmas →
    [Seleciona turma]
       │            │
 [Lança frequência] [Registra ocorrência]
        │            │
[Somente alunos/turma dele] (proteção via queryset/perm)

Facilitador loga →
     Vê só suas Atividades →
    [Seleciona Atividade]
       │            │
 [Lança frequência] [Registra ocorrência]
        │            │
[Somente alunos/Atividade dele] (proteção via queryset/perm)