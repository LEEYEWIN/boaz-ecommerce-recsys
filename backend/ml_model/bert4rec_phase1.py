import torch
import torch.nn as nn

class BERT4Rec(nn.Module):
    def __init__(self, vocab_size, max_seq_len=50, embed_size=128,
                 num_heads=4, num_layers=2, dropout=0.2):
        super().__init__()
        self.vocab_size  = vocab_size
        self.max_seq_len = max_seq_len

        self.item_embedding     = nn.Embedding(vocab_size, embed_size, padding_idx=0)
        self.position_embedding = nn.Embedding(max_seq_len, embed_size)

        self.layer_norm = nn.LayerNorm(embed_size)
        self.dropout    = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_size,
            nhead=num_heads,
            dim_feedforward=embed_size * 4,
            dropout=dropout,
            batch_first=True,
            norm_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.out = nn.Linear(embed_size, vocab_size)

    def forward(self, item_seqs):
        B, L      = item_seqs.shape
        positions = torch.arange(L, device=item_seqs.device).unsqueeze(0).expand(B, L)
        padding_mask = (item_seqs == 0)

        x = self.item_embedding(item_seqs) + self.position_embedding(positions)
        x = self.dropout(self.layer_norm(x))
        x = self.transformer(x, src_key_padding_mask=padding_mask)
        return self.out(x)
