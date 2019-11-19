class OpStream:
    def __init__(self, file):
        self.file = open(file)

    def read_op(self):
        line = self.file.readline()
        if not line:
            self.close()
            return None
        opcode = int(line.split()[0])
        value = int(line.split()[1], 0)
        return opcode, value

    def close(self):
        self.file.close()
